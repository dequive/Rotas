from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, model_validator

# STAB-F2/P1.1: canonical names are JournalItem* / JournalEntry*.
# Legacy names (ManualEntryCreate / ManualEntryItem / ManualEntryItemCreate) are
# kept ONLY as type aliases here so existing consumers import cleanly while
# P1.1 lands the rename across HR/Payables/Workshop.

# --- Contas e Lançamentos Base ---

class AccountResponse(BaseModel):
    id: UUID
    code: str
    name: str
    account_type: str
    parent_id: UUID | None = None

class JournalItemCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    account_id: UUID
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    third_party_id: UUID | None = None
    vehicle_id: UUID | None = None
    trip_id: UUID | None = None
    description: str | None = None

    @model_validator(mode='after')
    def validate_debit_credit(self):
        if self.debit < 0 or self.credit < 0:
            raise ValueError("Débito e Crédito não podem ser negativos")
        if self.debit == 0 and self.credit == 0:
            raise ValueError("Uma linha deve ter um débito ou crédito maior que zero")
        if self.debit > 0 and self.credit > 0:
            raise ValueError("Uma linha não pode ter simultaneamente débito e crédito")
        return self

class JournalItemResponse(BaseModel):
    id: UUID
    account_id: UUID
    debit: Decimal
    credit: Decimal
    third_party_id: UUID | None = None
    vehicle_id: UUID | None = None
    trip_id: UUID | None = None
    account: AccountResponse | None = None

# P1.1 will rename ManualEntryCreate → JournalEntryCreate.
# Today we keep the legacy name as a public alias (subclass) so external
# modules keep importing without churn.
class JournalEntryCreate(BaseModel):
    journal_type: str
    date: datetime | date_type
    reference: str | None = None
    description: str | None = None
    lines: list[JournalItemCreate] | None = None
    items: list[JournalItemCreate] | None = None

    @model_validator(mode='after')
    def _normalize_lines(self):
        if not self.lines and self.items:
            self.lines = self.items
        if not self.lines:
            raise ValueError("JournalEntryCreate requires 'lines' (or legacy 'items').")
        return self

class JournalEntryResponse(BaseModel):
    id: UUID
    journal_type: str
    date: datetime
    reference: str | None = None
    description: str | None = None
    status: str
    items: list[JournalItemResponse]
    source_document_type: str | None = None
    source_document_id: UUID | None = None

# --- Legacy aliases — kept only during P0 stabilisation ---
# TODO(stabilization/P1.1): remove these after HR/Payables/Workshop rename.
ManualEntryCreate = JournalEntryCreate
ManualEntryItem = JournalItemCreate
ManualEntryItemCreate = JournalItemCreate
JournalEntryLineCreate = JournalItemCreate

# --- Operações Manuais (legacy) ---
# Kept only because some schemas/tests reference it by name. The renamed
# canonical schema is JournalEntryCreate above.

class TrialBalanceLine(BaseModel):
    account_id: UUID
    code: str
    name: str
    debit_total: Decimal
    credit_total: Decimal
    balance: Decimal

class ProfitAndLossResponse(BaseModel):
    total_revenue: Decimal
    total_expense: Decimal
    ebitda: Decimal
    lines: list[TrialBalanceLine]
