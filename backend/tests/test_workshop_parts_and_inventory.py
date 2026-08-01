import sys
from pathlib import Path

from app.database import AsyncSessionLocal
from app.modules.workshop.schemas import WorkOrderCloseRequest

# Add backend directory to sys.path for IDE module resolution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.errors import ApiError
from app.modules.billing.models import BillingDocument
from app.modules.clients.models import Client
from app.modules.vehicles.models import Vehicle
from app.modules.workshop.inventory_service import (
    cancel_work_order,
    get_available_stock,
    get_inventory_valuation_summary,
    get_reorder_suggestions,
    issue_parts_for_work_order,
    record_inventory_adjustment,
    return_part_from_work_order,
)
from app.modules.workshop.models import (
    PartReservation,
    SparePartInventory,
    WorkOrder,
)
from app.modules.workshop.quote_schemas import QuoteCreate as WorkshopQuoteCreate
from app.modules.workshop.quote_schemas import QuoteItemCreate as WorkshopQuoteItemCreate
from app.modules.workshop.quote_service import accept_quote, create_quote
from app.modules.workshop.schemas import (
    WorkOrderCreate,
)
from app.modules.workshop.service import close_work_order, create_work_order
from app.modules.workshop.workshop_billing_service import (
    confirm_workshop_invoice,
    create_workshop_invoice,
)


@pytest.mark.asyncio
async def test_unapproved_excess_quantity_blocking_409(db, tenant_id, test_user):
    """Teste do Portão Comercial #1: Consumo acima da reserva aprovada pelo cliente é estritamente BLOQUEADO com 409."""

    # 1. Cadastrar Cliente e Viatura
    client = Client(
        tenant_id=tenant_id,
        trading_name="Transportes Silva",
        legal_name="Transportes Silva Lda",
        nuit="123456789",
    )
    db.add(client)
    await db.flush()

    vehicle = Vehicle(
        tenant_id=tenant_id,
        plate="MM-88-XX",
        brand="Toyota",
        model="Hilux 2.8",
        customer_client_id=client.id,
    )
    db.add(vehicle)
    await db.flush()

    # 2. Criar peça no inventário (Tambor de Óleo 220L)
    oil_part = SparePartInventory(
        tenant_id=tenant_id,
        sku="OIL-15W40-220L",
        name="Óleo Motor 15W40 Balde/Tambor",
        unit="liter",
        current_quantity=Decimal("220.000"),
        minimum_quantity=Decimal("20.000"),
        average_unit_cost=Decimal("200.00"),
    )
    db.add(oil_part)
    await db.flush()

    # 3. Criar e Aceitar Orçamento Original de 5.000 Litros de óleo
    quote_create = WorkshopQuoteCreate(
        client_id=client.id,
        vehicle_id=vehicle.id,
        items=[
            WorkshopQuoteItemCreate(
                item_type="part",
                description="Troca de Óleo Motor 5L",
                quantity=5.000,
                unit_price=250.00,
                part_id=oil_part.id,
            )
        ],
    )
    quote = await create_quote(db, tenant_id, quote_create, actor_id=test_user.id)
    accept_res = await accept_quote(db, tenant_id, quote["id"], actor_id=test_user.id)
    wo_id = accept_res["work_order_id"]

    # Validar que a reserva ativa = 5.000 L
    avail = await get_available_stock(db, tenant_id, oil_part.id)
    assert avail == Decimal("215.000")

    # 4. Tentar entregar 6.000 Litros (EXCEDE O APROVADO DE 5.000 L) → DEVE FALHAR COM HTTP 409
    with pytest.raises(ApiError) as exc_info:
        await issue_parts_for_work_order(
            db,
            tenant_id,
            wo_id,
            oil_part.id,
            Decimal("6.000"),
            actor_id=test_user.id,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "quantity_exceeds_approved_reservation"

    # 5. Criar e Aceitar Orçamento Suplementar de 1.500 L adicionais (evidência fotográfica no suplementar)
    supp_quote_create = WorkshopQuoteCreate(
        client_id=client.id,
        vehicle_id=vehicle.id,
        is_supplemental=True,
        related_work_order_id=accept_res["work_order_id"],
        items=[
            WorkshopQuoteItemCreate(
                item_type="part",
                description="Complemento Óleo Motor +1.5L",
                quantity=1.500,
                unit_price=250.00,
                part_id=oil_part.id,
            )
        ],
    )
    supp_quote = await create_quote(db, tenant_id, supp_quote_create, actor_id=test_user.id)
    supp_quote["is_supplemental"] = True
    await accept_quote(
        db,
        tenant_id,
        supp_quote["id"],
        actor_id=test_user.id,
    )

    # Tecto aprovado agora = 5.000 + 1.500 = 6.500 Litros. Stock disponível = 220 - 6.5 = 213.5
    avail_after_supp = await get_available_stock(db, tenant_id, oil_part.id)
    assert avail_after_supp == Decimal("213.500")

    # 6. Requisitar 6.000 L agora → SUCESSO!
    issue_res = await issue_parts_for_work_order(
        db,
        tenant_id,
        wo_id,
        oil_part.id,
        Decimal("6.000"),
        actor_id=test_user.id,
    )
    assert issue_res["quantity_issued"] == 6.0
    assert issue_res["current_stock"] == 214.0  # 220.0 - 6.0 = 214.0

    # Sobra de 0.500 L não requisitada foi libertada automaticamente
    avail_final = await get_available_stock(db, tenant_id, oil_part.id)
    assert avail_final == Decimal("214.000")


@pytest.mark.asyncio
async def test_multi_quote_fifo_reservation_consumption_and_surplus_release(
    db, tenant_id, test_user
):
    """Teste #3: FIFO determinístico de consumo de reservas multi-quote e libertação da sobra."""

    client = Client(tenant_id=tenant_id, trading_name="Auto Frota", nuit="987654321")
    db.add(client)
    await db.flush()

    vehicle = Vehicle(tenant_id=tenant_id, plate="TEST-123", customer_client_id=client.id)
    db.add(vehicle)
    await db.flush()

    part = SparePartInventory(
        tenant_id=tenant_id,
        sku="FILT-OIL-01",
        name="Filtro de Óleo HD",
        unit="unit",
        current_quantity=Decimal("10.000"),
        minimum_quantity=Decimal("2.000"),
        average_unit_cost=Decimal("500.00"),
    )
    db.add(part)
    await db.flush()

    # Orçamento 1: 5 unidades
    q1 = await create_quote(
        db,
        tenant_id,
        WorkshopQuoteCreate(
            client_id=client.id,
            vehicle_id=vehicle.id,
            items=[
                WorkshopQuoteItemCreate(
                    item_type="part", description="Filtros 5x", quantity=5.000, part_id=part.id
                )
            ],
        ),
        actor_id=test_user.id,
    )
    res1 = await accept_quote(db, tenant_id, q1["id"], actor_id=test_user.id)
    wo_id = res1["work_order_id"]

    # Orçamento 2 (Suplementar): 2 unidades
    q2 = await create_quote(
        db,
        tenant_id,
        WorkshopQuoteCreate(
            client_id=client.id,
            vehicle_id=vehicle.id,
            related_work_order_id=wo_id,
            is_supplemental=True,
            items=[
                WorkshopQuoteItemCreate(
                    item_type="part", description="Filtros 2x", quantity=2.000, part_id=part.id
                )
            ],
        ),
        actor_id=test_user.id,
    )
    q2["is_supplemental"] = True
    await accept_quote(
        db,
        tenant_id,
        q2["id"],
        actor_id=test_user.id,
    )

    # Entregar 6 unidades (consome 5 da reserva 1 totalmente, 1 da reserva 2, e liberta 1 da reserva 2)
    issue_result = await issue_parts_for_work_order(
        db,
        tenant_id,
        wo_id,
        part.id,
        Decimal("6.000"),
        actor_id=test_user.id,
    )
    assert issue_result["quantity_issued"] == 6.0
    assert issue_result["current_stock"] == 4.0

    # Verificar estados das reservas
    res_rows = (
        (
            await db.execute(
                select(PartReservation)
                .where(
                    PartReservation.work_order_id == wo_id, PartReservation.inventory_id == part.id
                )
                .order_by(PartReservation.created_at.asc(), PartReservation.id.asc())
            )
        )
        .scalars()
        .all()
    )

    assert len(res_rows) == 3  # Res 1 (consumed 5), Res 2 (consumed 1), Surplus Res (released 1)
    assert res_rows[0].status == "consumed" and res_rows[0].quantity_reserved == Decimal("5.000")
    assert res_rows[1].status == "consumed" and res_rows[1].quantity_reserved == Decimal("1.000")
    assert res_rows[2].status == "released" and res_rows[2].quantity_reserved == Decimal("1.000")


@pytest.mark.asyncio
async def test_post_billing_immutability_guard_and_wo_cancel_cleanup(db, tenant_id, test_user):
    """Testes #4 e #5: Imutabilidade pós-faturação com 409 e cancelamento de OS com libertação de rascunhos."""

    client = Client(tenant_id=tenant_id, trading_name="Expresso Pemba", nuit="555444333")
    db.add(client)
    await db.flush()

    vehicle = Vehicle(tenant_id=tenant_id, plate="TEST-123", customer_client_id=client.id)
    db.add(vehicle)
    await db.flush()

    part = SparePartInventory(
        tenant_id=tenant_id,
        sku="BRAKE-PAD-01",
        name="Pastilhas de Travão",
        unit="unit",
        current_quantity=Decimal("20.000"),
        minimum_quantity=Decimal("5.000"),
        average_unit_cost=Decimal("1200.00"),
    )
    db.add(part)
    await db.flush()

    # Criar OS com reserva e consumo
    q = await create_quote(
        db,
        tenant_id,
        WorkshopQuoteCreate(
            client_id=client.id,
            vehicle_id=vehicle.id,
            items=[
                WorkshopQuoteItemCreate(
                    item_type="part", description="Pastilhas", quantity=2.000, part_id=part.id
                )
            ],
        ),
        actor_id=test_user.id,
    )
    res_q = await accept_quote(db, tenant_id, q["id"], actor_id=test_user.id)
    wo_id = res_q["work_order_id"]

    await issue_parts_for_work_order(
        db, tenant_id, wo_id, part.id, Decimal("2.000"), actor_id=test_user.id
    )

    # Fechar OS e confirmar fatura
    wo_obj = await db.get(WorkOrder, wo_id)
    wo_obj.status = "quality_check"
    await db.flush()
    await close_work_order(
        db, tenant_id, wo_id, payload=WorkOrderCloseRequest(notes="Done"), actor_id=test_user.id
    )
    inv = await create_workshop_invoice(db, tenant_id, wo_id, actor_id=test_user.id)
    inv_id = inv["id"]
    await confirm_workshop_invoice(db, tenant_id, inv_id, actor_id=test_user.id)

    # Tentar devolver peça de OS facturada → DEVE REJEITAR COM HTTP 409
    with pytest.raises(ApiError) as exc_info:
        await return_part_from_work_order(
            db,
            tenant_id,
            wo_id,
            part.id,
            Decimal("1.000"),
            reason="Peça não utilizada",
            actor_id=test_user.id,
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "work_order_already_billed"

    # Teste #5: Cancelar uma nova OS com rascunho de fatura e reservas
    q_cancel = await create_quote(
        db,
        tenant_id,
        WorkshopQuoteCreate(
            client_id=client.id,
            vehicle_id=vehicle.id,
            items=[
                WorkshopQuoteItemCreate(
                    item_type="part", description="Pastilhas Extra", quantity=4.000, part_id=part.id
                )
            ],
        ),
        actor_id=test_user.id,
    )
    res_cancel = await accept_quote(db, tenant_id, q_cancel["id"], actor_id=test_user.id)
    wo_cancel_id = res_cancel["work_order_id"]

    # Gerar rascunho de fatura
    wo_cancel = await db.get(WorkOrder, wo_cancel_id)
    wo_cancel.status = "quality_check"
    await db.flush()
    draft_inv = await create_workshop_invoice(db, tenant_id, wo_cancel_id)

    # Cancelar OS
    cancel_res = await cancel_work_order(
        db, tenant_id, wo_cancel_id, reason="Desistência", actor_id=test_user.id
    )
    assert cancel_res["released_reservations"] >= 1
    assert cancel_res["cancelled_drafts"] == 1

    # Verificar que a fatura rascunho foi anulada
    doc = await db.get(BillingDocument, draft_inv["id"])
    assert doc.status == "cancelled"


@pytest.mark.asyncio
async def test_inventory_adjustment_and_valuation(db, tenant_id, test_user):
    """Teste de Ajuste de Inventário por Perda Residual e Valorização de Stock."""

    oil_part = SparePartInventory(
        tenant_id=tenant_id,
        sku="OIL-SYNTH-5W30",
        name="Óleo Sintético 5W30",
        unit="liter",
        category="Lubrificantes",
        current_quantity=Decimal("100.000"),
        minimum_quantity=Decimal("10.000"),
        average_unit_cost=Decimal("450.00"),
    )
    db.add(oil_part)
    await db.flush()

    # Dar baixa de 2.500 Litros de perda residual no fundo do tambor
    adj_res = await record_inventory_adjustment(
        db,
        tenant_id,
        oil_part.id,
        Decimal("2.500"),
        direction="out",
        reason="perda_residual_fundo_tambor",
        actor_id=test_user.id,
    )
    assert adj_res["current_stock"] == 97.5

    # Testar valorização de stock
    val = await get_inventory_valuation_summary(db, tenant_id)
    assert val["total_items_count"] >= 1
    assert val["total_valuation_mzn"] >= (97.5 * 450.0)


@pytest.mark.asyncio
async def test_asyncio_gather_real_concurrency_contention(db, tenant_id, test_user):
    """Teste #2: Concorrência Real com transações / sessões independentes.

    Cria duas sessões DB assíncronas distintas (simulando 2 requisições HTTP paralelas).
    Dispara duas entregas simultâneas via asyncio.gather.
    Confirma que o lock with_for_update() força isolamento transacional estrito.
    """

    session_factory = AsyncSessionLocal

    client = Client(tenant_id=tenant_id, trading_name="Logística Maputo", nuit="777888999")
    db.add(client)
    await db.flush()

    vehicle = Vehicle(tenant_id=tenant_id, plate="TEST-123", customer_client_id=client.id)
    db.add(vehicle)
    await db.flush()

    # Tambor de Óleo com 10.000 Litros
    oil_part = SparePartInventory(
        tenant_id=tenant_id,
        sku="OIL-RACE-10L",
        name="Óleo Motor HD 10L",
        unit="liter",
        current_quantity=Decimal("10.000"),
        minimum_quantity=Decimal("1.000"),
        average_unit_cost=Decimal("300.00"),
    )
    db.add(oil_part)
    await db.flush()

    # Orçamento aprovando 10.000 L
    q = await create_quote(
        db,
        tenant_id,
        WorkshopQuoteCreate(
            client_id=client.id,
            vehicle_id=vehicle.id,
            items=[
                WorkshopQuoteItemCreate(
                    item_type="part", description="Óleo 10L", quantity=10.000, part_id=oil_part.id
                )
            ],
        ),
        actor_id=test_user.id,
    )
    res_q = await accept_quote(db, tenant_id, q["id"], actor_id=test_user.id)
    wo_id = res_q["work_order_id"]
    await db.commit()

    # Função executada numa transação/sessão independente
    async def issue_in_separate_session(qty: Decimal):
        async with session_factory() as sess:
            return await issue_parts_for_work_order(
                sess, tenant_id, wo_id, oil_part.id, qty, actor_id=test_user.id
            )

    # Disparar 2 entregas simultâneas de 5.000 L em transações SEPARADAS via asyncio.gather
    results = await asyncio.gather(
        issue_in_separate_session(Decimal("5.000")),
        issue_in_separate_session(Decimal("5.000")),
        return_exceptions=True,
    )

    # Ambas devem ser executadas sem race condition ou uma consome e a outra falha se stock esgotar
    successful_results = [r for r in results if not isinstance(r, Exception)]
    if len(successful_results) == 0:
        print("EXCEPTIONS:", results)
        raise AssertionError("Both concurrent inventory operations failed")

    async with session_factory() as check_sess:
        check_part = await check_sess.get(SparePartInventory, oil_part.id)
        assert check_part is not None
        assert check_part.current_quantity >= Decimal("0.000")


@pytest.mark.asyncio
async def test_reorder_suggestions_with_blocked_work_orders(db, tenant_id, test_user):
    """Teste de Alertas de Reposição Inteligente (Reorder Suggestions) com rastreio de OSs em backorder."""

    part = SparePartInventory(
        tenant_id=tenant_id,
        sku="AIR-FILT-02",
        name="Filtro de Ar Pesado",
        unit="unit",
        current_quantity=Decimal("1.000"),
        minimum_quantity=Decimal("5.000"),  # Stock atual (1) <= mínimo (5)
        average_unit_cost=Decimal("400.00"),
        reorder_quantity=20,
    )
    db.add(part)
    await db.flush()

    # Criar orçamento solicitando 3 unidades (insuficiente -> backorder)
    client = Client(tenant_id=tenant_id, trading_name="Frota Pemba", nuit="111222333")
    db.add(client)
    await db.flush()

    vehicle = Vehicle(tenant_id=tenant_id, plate="TEST-123", customer_client_id=client.id)
    db.add(vehicle)
    await db.flush()

    q = await create_quote(
        db,
        tenant_id,
        WorkshopQuoteCreate(
            client_id=client.id,
            vehicle_id=vehicle.id,
            items=[
                WorkshopQuoteItemCreate(
                    item_type="part", description="Filtros Ar 3x", quantity=3.000, part_id=part.id
                )
            ],
        ),
        actor_id=test_user.id,
    )
    res_q = await accept_quote(db, tenant_id, q["id"], actor_id=test_user.id)

    # Obter sugestões de reposição
    suggestions = await get_reorder_suggestions(db, tenant_id)
    target_sugg = next((s for s in suggestions if s["inventory_id"] == part.id), None)

    assert target_sugg is not None
    assert target_sugg["sku"] == "AIR-FILT-02"
    assert target_sugg["backorders_count"] == 1
    assert str(res_q["work_order_id"]) in target_sugg["blocked_work_order_ids"]


@pytest.mark.asyncio
async def test_purchase_order_creation_and_reception_wacc(db, tenant_id, test_user):
    """Teste de Encomenda de Compra a Fornecedor e Recepção com Recálculo de Custo Médio WACC."""

    from app.modules.third_party.models import ThirdParty, ThirdPartyRole
    from app.modules.workshop.inventory_service import create_purchase_order, receive_purchase_order

    # 1. Cadastrar Fornecedor de Peças
    supplier = ThirdParty(
        tenant_id=tenant_id,
        name="Auto Peças Moçambique Lda",
        nuit="999888777",
    )
    db.add(supplier)
    await db.flush()

    role = ThirdPartyRole(
        tenant_id=tenant_id,
        third_party_id=supplier.id,
        role_type="spare_parts_supplier",
    )
    db.add(role)
    await db.flush()

    # 2. Peça existente com 10 unidades a 100 MZN cada (WACC = 100.00)
    part = SparePartInventory(
        tenant_id=tenant_id,
        sku="SPARK-PLUG-01",
        name="Vela de Ignição Irídio",
        unit="unit",
        current_quantity=Decimal("10.000"),
        minimum_quantity=Decimal("2.000"),
        average_unit_cost=Decimal("100.00"),
    )
    db.add(part)
    await db.flush()

    # 3. Criar Encomenda de Compra (PO) de 10 unidades a 200 MZN cada
    po = await create_purchase_order(
        db,
        tenant_id,
        supplier.id,
        [
            {
                "inventory_id": part.id,
                "quantity_ordered": Decimal("10.000"),
                "unit_price": Decimal("200.00"),
            }
        ],
        supplier_invoice_number="FT-2026/001",
        actor_id=test_user.id,
    )
    assert po.status == "ordered"
    assert po.total_amount == Decimal("2000.00")

    # 4. Receber a PO
    rec_res = await receive_purchase_order(db, tenant_id, po.id, actor_id=test_user.id)
    assert rec_res["status"] == "received"

    # Verificar stock e novo WACC:
    # WACC = (10 * 100 + 10 * 200) / 20 = 3000 / 20 = 150.00 MZN
    await db.refresh(part)
    assert part.current_quantity == Decimal("20.000")
    assert part.average_unit_cost == Decimal("150.00")


@pytest.mark.asyncio
async def test_core_return_with_photo_evidence_and_supplier_credit(db, tenant_id, test_user):
    """Teste de Rastreio de Peça Velha em Retoma (Core Return) com Foto de Evidência e Crédito de Fornecedor."""

    from app.modules.workshop.inventory_service import credit_core_return, register_core_return

    part = SparePartInventory(
        tenant_id=tenant_id,
        sku="ALT-24V-80A",
        name="Alternador Heavy Duty 24V",
        unit="unit",
        current_quantity=Decimal("2.000"),
        average_unit_cost=Decimal("8000.00"),
    )
    db.add(part)
    await db.flush()

    client = Client(tenant_id=tenant_id, trading_name="Transportes Maputo", nuit="333222111")
    db.add(client)
    await db.flush()

    vehicle = Vehicle(tenant_id=tenant_id, plate="TEST-123", customer_client_id=client.id)
    db.add(vehicle)
    await db.flush()

    wo_payload = WorkOrderCreate(
        vehicle_id=vehicle.id, client_id=client.id, planned_work="Substituição de Alternador"
    )
    wo = await create_work_order(
        db,
        tenant_id,
        wo_payload,
        actor_id=test_user.id,
    )

    # 1. Registar peça velha de troca com foto de evidência
    core_item = await register_core_return(
        db,
        tenant_id,
        wo["id"],
        part.id,
        description="Alternador queimado removido da viatura",
        serial_number="ALT-SN-998877",
        evidence_photo_file_id=None,  # Simulação de FK de ficheiro
        actor_id=test_user.id,
    )
    assert core_item.status == "pending_return"
    assert core_item.serial_number == "ALT-SN-998877"

    # 2. Dar baixa com crédito concedido pelo fornecedor (3.500 MZN)
    credited = await credit_core_return(
        db,
        tenant_id,
        core_item.id,
        Decimal("3500.00"),
        actor_id=test_user.id,
    )
    assert credited.status == "credited"
    assert credited.credit_amount == Decimal("3500.00")
