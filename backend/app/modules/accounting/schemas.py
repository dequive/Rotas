from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal

# --- Contas e Lançamentos Base ---

class AccountResponse(BaseModel):
    id: UUID
    code: str
    name: str
    account_type: str
    parent_id: Optional[UUID] = None

class JournalItemCreate(BaseModel):
    account_id: UUID
    debit: Decimal = Decimal("0.00")
    credit: Decimal = Decimal("0.00")
    third_party_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    trip_id: Optional[UUID] = None

class JournalItemResponse(BaseModel):
    id: UUID
    account_id: UUID
    debit: Decimal
    credit: Decimal
    third_party_id: Optional[UUID] = None
    vehicle_id: Optional[UUID] = None
    trip_id: Optional[UUID] = None
    account: Optional[AccountResponse] = None

class JournalEntryResponse(BaseModel):
    id: UUID
    journal_type: str
    date: datetime
    reference: Optional[str] = None
    description: Optional[str] = None
    status: str
    items: List[JournalItemResponse]

# --- Operações Manuais ---

class ManualEntryCreate(BaseModel):
    journal_type: str  # "OD", "VEN", "COM", "TES"
    date: datetime
    reference: Optional[str] = None
    description: str
    items: List[JournalItemCreate]

# --- Mapas de Gestão (DRE e Balancete) ---

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
    lines: List[TrialBalanceLine]
