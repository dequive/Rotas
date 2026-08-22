from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TenantPrincipal as Principal
from app.core.deps import get_session
from app.core.idempotency import execute_http_idempotent
from app.core.openapi_responses import PDF_RESPONSE
from app.core.rbac import (
    PAYABLES_PAY,
    PAYABLES_READ,
    PAYABLES_WRITE,
    require_permission,
)
from app.modules.accounting.models import Account
from app.modules.accounting.schemas import JournalEntryCreate, JournalItemCreate
from app.modules.accounting.services import create_journal_entry
from app.modules.audit.service import record_audit_log
from app.modules.payables.models import PurchaseOrder, SupplierInvoice, SupplierPayment
from app.modules.payables.pdf_templates import generate_purchase_order_pdf
from app.modules.payables.schemas import (
    InvoicePaymentRequest,
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    SupplierInvoiceCreate,
    SupplierInvoiceResponse,
    SupplierPaymentCreate,
    SupplierPaymentResponse,
)
from app.modules.tenants.models import Tenant, TenantDocumentProfile
from app.modules.third_party.models import ThirdParty

router = APIRouter(prefix="/payables", tags=["payables"])


@router.post("/purchase-orders", response_model=PurchaseOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    principal: Annotated[Principal, Depends(require_permission(PAYABLES_WRITE))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
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
    principal: Annotated[Principal, Depends(require_permission(PAYABLES_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
    third_party_id: UUID | None = None,
):
    stmt = select(PurchaseOrder).where(PurchaseOrder.tenant_id == principal.tenant_id)
    if third_party_id:
        stmt = stmt.where(PurchaseOrder.third_party_id == third_party_id)
    result = await session.execute(stmt.order_by(PurchaseOrder.created_at.desc()))
    return list(result.scalars().all())


@router.get("/purchase-orders/{po_id}/pdf", responses=PDF_RESPONSE)
async def download_purchase_order_pdf(
    po_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(PAYABLES_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    po = await session.get(PurchaseOrder, po_id)
    if not po or po.tenant_id != principal.tenant_id:
        raise HTTPException(status_code=404, detail="Requisição não encontrada")

    supplier = await session.get(ThirdParty, po.third_party_id)
    tenant = await session.get(Tenant, principal.tenant_id)
    prof_result = await session.execute(
        select(TenantDocumentProfile).where(TenantDocumentProfile.tenant_id == principal.tenant_id)
    )
    profile = prof_result.scalar_one_or_none()

    pdf_bytes = generate_purchase_order_pdf(tenant, profile, po, supplier)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="PO_{po.po_number}.pdf"'},
    )


@router.post("/invoices", response_model=SupplierInvoiceResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_invoice(
    payload: SupplierInvoiceCreate,
    principal: Annotated[Principal, Depends(require_permission(PAYABLES_WRITE))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
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
    principal: Annotated[Principal, Depends(require_permission(PAYABLES_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
    third_party_id: UUID | None = None,
):
    stmt = select(SupplierInvoice).where(SupplierInvoice.tenant_id == principal.tenant_id)
    if third_party_id:
        stmt = stmt.where(SupplierInvoice.third_party_id == third_party_id)
    result = await session.execute(stmt.order_by(SupplierInvoice.created_at.desc()))
    return list(result.scalars().all())


@router.post("/payments", response_model=SupplierPaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier_payment(
    payload: SupplierPaymentCreate,
    principal: Annotated[Principal, Depends(require_permission(PAYABLES_PAY))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
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
async def list_supplier_payments(
    principal: Annotated[Principal, Depends(require_permission(PAYABLES_READ))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(
        select(SupplierPayment)
        .where(SupplierPayment.tenant_id == principal.tenant_id)
        .order_by(SupplierPayment.created_at.desc())
    )
    return list(result.scalars().all())


@router.post("/invoices/{invoice_id}/pay", response_model=SupplierPaymentResponse)
async def pay_supplier_invoice(
    invoice_id: UUID,
    payload: InvoicePaymentRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    principal: Annotated[Principal, Depends(require_permission(PAYABLES_PAY))],
    session: Annotated[AsyncSession, Depends(get_session)],
):
    async def settle_invoice() -> dict:
        invoice = await session.scalar(
            select(SupplierInvoice)
            .where(
                SupplierInvoice.id == invoice_id,
                SupplierInvoice.tenant_id == principal.tenant_id,
            )
            .with_for_update()
        )
        if not invoice:
            raise HTTPException(status_code=404, detail="Fatura de Fornecedor não encontrada")
        if invoice.status == "paid":
            raise HTTPException(status_code=409, detail="Esta fatura já foi paga")

        paid_total = await session.scalar(
            select(func.coalesce(func.sum(SupplierPayment.amount), Decimal("0.00"))).where(
                SupplierPayment.tenant_id == principal.tenant_id,
                SupplierPayment.invoice_id == invoice.id,
                SupplierPayment.status == "confirmed",
            )
        )
        remaining = invoice.amount - Decimal(str(paid_total or 0))
        if payload.amount > remaining:
            raise HTTPException(
                status_code=409,
                detail=f"Pagamento excede o saldo pendente de {remaining} {invoice.currency}",
            )

        accounts_by_code = {
            account.code: account
            for account in (
                await session.scalars(
                    select(Account).where(
                        Account.tenant_id == principal.tenant_id,
                        Account.code.in_(("4.2", "1.2", "42", "12")),
                    )
                )
            ).all()
        }
        payable_account = accounts_by_code.get("4.2") or accounts_by_code.get("42")
        bank_account = accounts_by_code.get("1.2") or accounts_by_code.get("12")
        if not payable_account or not bank_account:
            raise HTTPException(
                status_code=409,
                detail="Plano de contas incompleto: contas 4.2 e 1.2 são obrigatórias",
            )

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
            status="confirmed",
        )
        session.add(payment)
        await session.flush()

        new_paid_total = Decimal(str(paid_total or 0)) + payload.amount
        invoice.status = "paid" if new_paid_total == invoice.amount else "partially_paid"

        entry_payload = JournalEntryCreate(
            journal_type="TES",
            date=payload.value_date,
            description=f"Liquidação de Fatura {invoice.invoice_number or invoice.id}",
            reference=payload.reference,
            items=[
                JournalItemCreate(
                    account_id=payable_account.id,
                    debit=payload.amount,
                    credit=Decimal("0.00"),
                ),
                JournalItemCreate(
                    account_id=bank_account.id,
                    debit=Decimal("0.00"),
                    credit=payload.amount,
                ),
            ],
        )

        await create_journal_entry(
            session,
            tenant_id=principal.tenant_id,
            payload=entry_payload,
            actor_id=principal.user_id,
            source_type="supplier_payment",
            source_id=payment.id,
        )
        await record_audit_log(
            session,
            tenant_id=principal.tenant_id,
            user_id=principal.user_id,
            action="payables.supplier_payment.created",
            entity_type="supplier_payment",
            entity_id=payment.id,
            new_values={
                "invoice_id": str(invoice.id),
                "amount": str(payment.amount),
                "invoice_status": invoice.status,
            },
        )
        await session.flush()
        await session.refresh(payment)
        return SupplierPaymentResponse.model_validate(payment).model_dump(mode="json")

    return await execute_http_idempotent(
        session,
        tenant_id=principal.tenant_id,
        user_id=principal.user_id,
        idempotency_key=idempotency_key,
        operation="payables.supplier_invoice.pay",
        entity_type="supplier_payment",
        payload={"invoice_id": invoice_id, **payload.model_dump()},
        handler=settle_invoice,
    )
