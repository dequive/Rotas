from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------
# Employees
# ---------------------------------------------------------
class EmployeeCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=80)
    department: str = Field(min_length=1, max_length=80)
    base_salary: float = Field(ge=0)
    
    employee_number: str | None = Field(default=None, max_length=40)
    inss_beneficiary_number: str | None = Field(default=None, max_length=80)
    professional_category: str | None = Field(default=None, max_length=100)
    irps_tax_percentage: float = Field(default=0, ge=0, le=100)
    
    nif_nuit: str | None = Field(default=None, max_length=40)
    bank_account_nib: str | None = Field(default=None, max_length=80)
    date_of_birth: date | None = None
    hire_date: date
    
    driver_id: UUID | None = None
    user_id: UUID | None = None


class EmployeeUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: str | None = Field(default=None, min_length=1, max_length=80)
    department: str | None = Field(default=None, min_length=1, max_length=80)
    base_salary: float | None = Field(default=None, ge=0)
    
    employee_number: str | None = Field(default=None, max_length=40)
    inss_beneficiary_number: str | None = Field(default=None, max_length=80)
    professional_category: str | None = Field(default=None, max_length=100)
    irps_tax_percentage: float | None = Field(default=None, ge=0, le=100)
    
    status: str | None = Field(default=None, max_length=30)
    termination_date: date | None = None


class EmployeeResponse(EmployeeCreate):
    id: UUID
    tenant_id: UUID
    status: str
    termination_date: date | None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Documents
# ---------------------------------------------------------
class EmployeeDocumentCreate(BaseModel):
    document_type: str = Field(min_length=1, max_length=80)
    document_number: str | None = Field(default=None, max_length=80)
    issued_at: date | None = None
    expiry_date: date | None = None
    notes: str | None = None


class EmployeeDocumentResponse(EmployeeDocumentCreate):
    id: UUID
    employee_id: UUID
    tenant_id: UUID
    status: str
    file_id: UUID | None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Payroll
# ---------------------------------------------------------
class EmployeePayrollVariables(BaseModel):
    employee_id: UUID
    overtime_hours: Decimal = Field(default=Decimal("0.00"), ge=0)
    meal_allowance_days: Decimal = Field(default=Decimal("0.00"), ge=0)
    other_allowances: Decimal = Field(default=Decimal("0.00"), ge=0)
    bonus: Decimal = Field(default=Decimal("0.00"), ge=0)


class PayrollGenerationRequest(BaseModel):
    period_month: int = Field(ge=1, le=12)
    period_year: int = Field(ge=2020)
    employee_id: UUID | None = None 
    variables: list[EmployeePayrollVariables] | None = None


class PayrollSlipLineResponse(BaseModel):
    id: UUID
    payroll_slip_id: UUID
    code: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal
    irps_tax_percentage: Decimal | None
    is_taxable_inss: bool
    is_taxable_syndicate: bool
    
    model_config = ConfigDict(from_attributes=True)


class PayrollSlipResponse(BaseModel):
    id: UUID
    employee_id: UUID
    tenant_id: UUID
    period_month: int
    period_year: int
    
    gross_salary: Decimal
    total_inss: Decimal
    total_irps: Decimal
    total_syndicate: Decimal
    total_deductions: Decimal
    net_salary: Decimal
    
    status: str
    payment_date: date | None
    notes: str | None
    
    created_at: datetime
    updated_at: datetime
    
    # We will eager load or attach the lines here
    lines: List[PayrollSlipLineResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------
# Salary Advances (Vales)
# ---------------------------------------------------------
class SalaryAdvanceCreate(BaseModel):
    employee_id: UUID
    amount: Decimal = Field(ge=0.01)
    date_requested: date
    reason: str | None = None


class SalaryAdvanceResponse(SalaryAdvanceCreate):
    id: UUID
    tenant_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
