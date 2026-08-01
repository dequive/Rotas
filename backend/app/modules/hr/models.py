import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Employee(Base):
    __tablename__ = "employees"
    __table_args__ = (UniqueConstraint("tenant_id", "nif_nuit", name="uq_employees_tenant_nif"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), index=True, nullable=False
    )

    # Optional link to a driver profile
    driver_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("drivers.id", ondelete="SET NULL"), index=True, nullable=True
    )
    # Optional link to a user login
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(
        String(80), nullable=False
    )  # e.g. "driver", "mechanic", "manager"
    department: Mapped[str] = mapped_column(String(80), nullable=False)

    # Detalhes de Cadastro PHC-Like
    employee_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    inss_beneficiary_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    professional_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    irps_tax_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, nullable=False)

    base_salary: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    nif_nuit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bank_account_nib: Mapped[str | None] = mapped_column(String(80), nullable=True)

    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False, default=func.current_date())
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(
        String(30), default="active", index=True
    )  # active, on_leave, terminated
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EmployeeDocument(Base):
    __tablename__ = "employee_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), index=True, nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), index=True, nullable=False
    )

    document_type: Mapped[str] = mapped_column(
        String(80), nullable=False
    )  # "id_card", "passport", "contract", "health_card"
    document_number: Mapped[str | None] = mapped_column(String(80), nullable=True)

    issued_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, index=True, nullable=True)
    file_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # link to s3 file

    status: Mapped[str] = mapped_column(String(30), default="valid", index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Absence(Base):
    __tablename__ = "absences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), index=True, nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), index=True, nullable=False
    )

    absence_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # "vacation", "sick_leave", "unjustified"
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    is_paid: Mapped[bool] = mapped_column(Boolean, default=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PayrollSlip(Base):
    __tablename__ = "payroll_slips"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "employee_id",
            "period_month",
            "period_year",
            name="uq_payroll_slips_tenant_emp_period",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), index=True, nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id"), index=True, nullable=False
    )

    period_month: Mapped[int] = mapped_column(nullable=False)
    period_year: Mapped[int] = mapped_column(nullable=False)

    gross_salary: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )  # Iliquido
    total_inss: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # Taxa Social
    total_irps: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # IRPS
    total_syndicate: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # Sindicato
    total_deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)  # Total Descontos
    net_salary: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )  # Liquido a Receber

    status: Mapped[str] = mapped_column(
        String(30), default="draft", index=True
    )  # draft, approved, paid
    payment_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    lines: Mapped[list["PayrollSlipLine"]] = relationship(
        "PayrollSlipLine",
        back_populates="payroll_slip",
        cascade="all, delete-orphan",
    )


class PayrollCode(Base):
    __tablename__ = "payroll_codes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), index=True, nullable=False
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. R01, D01
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. Remuneração Mensal
    code_type: Mapped[str] = mapped_column(String(20), nullable=False)  # earning, deduction

    is_taxable_inss: Mapped[bool] = mapped_column(Boolean, default=False)
    is_taxable_irps: Mapped[bool] = mapped_column(Boolean, default=False)
    is_taxable_syndicate: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PayrollSlipLine(Base):
    __tablename__ = "payroll_slip_lines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), index=True, nullable=False
    )
    payroll_slip_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_slips.id", ondelete="CASCADE"), index=True, nullable=False
    )

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(String(100), nullable=False)

    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    amount: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False
    )  # Can be negative for deductions

    irps_tax_percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_taxable_inss: Mapped[bool] = mapped_column(Boolean, default=False)
    is_taxable_syndicate: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    payroll_slip: Mapped["PayrollSlip"] = relationship(
        "PayrollSlip",
        back_populates="lines",
    )


class SalaryAdvance(Base):
    __tablename__ = "salary_advances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id"), index=True, nullable=False
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), index=True, nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    date_requested: Mapped[date] = mapped_column(Date, nullable=False, default=func.current_date())

    status: Mapped[str] = mapped_column(
        String(30), default="pending", index=True
    )  # pending, approved, rejected, deducted
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
