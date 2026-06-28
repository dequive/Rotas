from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, get_current_principal
from app.core.deps import get_session
from app.modules.payables.models import PurchaseOrder, SupplierInvoice, SupplierPayment
from app.modules.payables.pdf_templates import generate_purchase_order_pdf
from app.modules.tenants.models import Tenant, TenantDocumentProfile
from app.modules.third_parties.models import ThirdParty
from app.modules.payables.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    SupplierInvoiceCreate,
    SupplierInvoiceResponse,
    SupplierPaymentCreate,
    SupplierPaymentResponse,
    InvoicePaymentRequest,
)
from app.modules.accounting.services import create_journal_entry
from app.modules.accounting.schemas import ManualEntryCreate, ManualEntryItem

router = APIRouter(prefix="/payables", tags=["payables"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
PrincipalDep = Annotated[Principal, Depends(get_current_principal)]


@router.post("/purchase-orders", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    session: SessionDep,
    principal: PrincipalDep,
) -> PurchaseOrder:
    po = PurchaseOrder(
        tenant_id=principal.tenant_id,
        **payload.model_dump(),
    )
    session.add(po)
    await session.commit()
    await session.refresh(po)
    return po


@router.get("/purchase-orders", response_model=list[PurchaseOrderResponse])
async def list_purchase_orders(
    session: SessionDep,
    third_party_id: UUID | None = None,
) -> list[PurchaseOrder]:
    stmt = select(PurchaseOrder)
    if third_party_id:
        stmt = stmt.where(PurchaseOrder.third_party_id == third_party_id)
    result = await session.execute(stmt.order_by(PurchaseOrder.created_at.desc()))
    return list(result.scalars().all())


@router.get("/purchase-orders/{po_id}/pdf")
async def download_purchase_order_pdf(
    po_id: UUID,
    session: SessionDep,
    principal: PrincipalDep,
) -> Response:
    # 1. Obter a Requisição
    po = await session.get(PurchaseOrder, po_id)
    if not po or po.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Requisição não encontrada")
        
    # 2. Obter o Fornecedor (ThirdParty)
    supplier = await session.get(ThirdParty, po.third_party_id)
    
    # 3. Obter dados do Tenant e Document Profile (White-Label)
    tenant = await session.get(Tenant, principal.tenant_id)
    prof_result = await session.execute(select(TenantDocumentProfile).where(TenantDocumentProfile.tenant_id == principal.tenant_id))
    profile = prof_result.scalar_one_or_none()
    
    # 4. Gerar o PDF
    pdf_bytes = generate_purchase_order_pdf(tenant, profile, po, supplier)
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="PO_{po.po_number}.pdf"'}
    )


@router.post("/invoices", response_model=SupplierInvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_invoice(
    payload: SupplierInvoiceCreate,
    session: SessionDep,
    principal: PrincipalDep,
) -> SupplierInvoice:
    invoice = SupplierInvoice(
        tenant_id=principal.tenant_id,
        **payload.model_dump(),
    )
    session.add(invoice)
    await session.commit()
    await session.refresh(invoice)
    return invoice


@router.get("/invoices", response_model=list[SupplierInvoiceResponse])
async def list_supplier_invoices(
    session: SessionDep,
    third_party_id: UUID | None = None,
) -> list[SupplierInvoice]:
    stmt = select(SupplierInvoice)
    if third_party_id:
        stmt = stmt.where(SupplierInvoice.third_party_id == third_party_id)
    result = await session.execute(stmt.order_by(SupplierInvoice.created_at.desc()))
    return list(result.scalars().all())


@router.post("/payments", response_model=SupplierPaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_payment(
    payload: SupplierPaymentCreate,
    session: SessionDep,
    principal: PrincipalDep,
) -> SupplierPayment:
    payment = SupplierPayment(
        tenant_id=principal.tenant_id,
        created_by=principal.user_id,
        **payload.model_dump(),
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment


@router.get("/payments", response_model=list[SupplierPaymentResponse])
async def list_supplier_payments(session: SessionDep) -> list[SupplierPayment]:
    result = await session.execute(select(SupplierPayment).order_by(SupplierPayment.created_at.desc()))
    return list(result.scalars().all())


@router.post("/invoices/{invoice_id}/pay", response_model=SupplierPaymentResponse)
async def pay_supplier_invoice(
    invoice_id: UUID,
    payload: InvoicePaymentRequest,
    session: SessionDep,
    principal: PrincipalDep,
) -> SupplierPayment:
    # 1. Obter a Fatura
    invoice = await session.get(SupplierInvoice, invoice_id)
    if not invoice or invoice.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Fatura de Fornecedor não encontrada")
    if invoice.status == "paid":
        raise HTTPException(status_code=400, detail="Esta fatura já foi paga")
        
    # 2. Registar o Pagamento
    payment = SupplierPayment(
        tenant_id=principal.tenant_id,
        third_party_id=invoice.third_party_id,
        invoice_id=invoice.id,
        amount=payload.amount,
        currency=invoice.currency,
        value_date=payload.value_date,
        payment_method=payload.payment_method,
        reference=payload.reference,
        notes=payload.notes,
        created_by=principal.user_id,
        status="confirmed"
    )
    session.add(payment)
    
    # 3. Atualizar Fatura
    if payload.amount >= invoice.amount:
        invoice.status = "paid"
    else:
        invoice.status = "partially_paid" # assuming the schema accepts this
        
    # 4. Magia Contabilística: Saída de Bancos, Abate em Fornecedores
    entry_payload = ManualEntryCreate(
        date=payload.value_date,
        description=f"Liquidação de Fatura {invoice.invoice_number or invoice.id}",
        reference=payload.reference,
        items=[
            ManualEntryItem(
                account_id=None,
                account_number="42", # Fornecedores
                amount=payload.amount,
                type="debit"
            ),
            ManualEntryItem(
                account_id=None,
                account_number="12", # Bancos
                amount=payload.amount,
                type="credit"
            )
        ]
    )
    
    # Executa o Lançamento
    await create_journal_entry(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        source_type="supplier_payment",
        source_id=payment.id,
        payload=entry_payload
    )
    
    await session.commit()
    await session.refresh(payment)
    return payment
