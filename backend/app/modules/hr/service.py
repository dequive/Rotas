import calendar
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.accounting.models import Account
from app.modules.accounting.schemas import JournalEntryCreate, JournalItemCreate
from app.modules.accounting.services import create_journal_entry
from app.modules.hr.models import (
    Absence,
    Employee,
    EmployeeDocument,
    PayrollSlip,
    PayrollSlipLine,
    SalaryAdvance,
)
from app.modules.hr.schemas import EmployeeCreate, EmployeeDocumentCreate, PayrollGenerationRequest


def _decimal(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


# ------------------------------------------------------------------
# Employee Core
# ------------------------------------------------------------------
async def list_employees(tenant_id: UUID, db: AsyncSession) -> Sequence[Employee]:
    result = await db.execute(
        select(Employee)
        .where(Employee.tenant_id == tenant_id)
        .order_by(Employee.first_name, Employee.last_name)
    )
    return result.scalars().all()


async def get_employee(tenant_id: UUID, employee_id: UUID, db: AsyncSession) -> Employee:
    emp = await db.get(Employee, employee_id)
    if not emp or emp.tenant_id != tenant_id:
        raise ApiError(
            "EMPLOYEE_NOT_FOUND",
            "Colaborador não encontrado.",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return emp


async def create_employee(tenant_id: UUID, payload: EmployeeCreate, db: AsyncSession) -> Employee:
    if payload.nif_nuit:
        stmt = select(Employee).where(
            Employee.tenant_id == tenant_id, Employee.nif_nuit == payload.nif_nuit
        )
        if await db.scalar(stmt):
            raise ApiError(
                "NUIT_EXISTS",
                "Já existe um colaborador com este NUIT.",
                status_code=status.HTTP_400_BAD_REQUEST,
            )

    emp = Employee(
        tenant_id=tenant_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=payload.role,
        department=payload.department,
        employee_number=payload.employee_number,
        inss_beneficiary_number=payload.inss_beneficiary_number,
        professional_category=payload.professional_category,
        irps_tax_percentage=_decimal(payload.irps_tax_percentage),
        base_salary=_decimal(payload.base_salary),
        nif_nuit=payload.nif_nuit,
        bank_account_nib=payload.bank_account_nib,
        date_of_birth=payload.date_of_birth,
        hire_date=payload.hire_date,
        driver_id=payload.driver_id,
        user_id=payload.user_id,
    )
    db.add(emp)
    await db.commit()
    await db.refresh(emp)
    return emp


# ------------------------------------------------------------------
# Documents
# ------------------------------------------------------------------
async def list_employee_documents(
    tenant_id: UUID, employee_id: UUID, db: AsyncSession
) -> Sequence[EmployeeDocument]:
    # Ensure employee exists
    await get_employee(tenant_id, employee_id, db)

    result = await db.execute(
        select(EmployeeDocument)
        .where(EmployeeDocument.tenant_id == tenant_id, EmployeeDocument.employee_id == employee_id)
        .order_by(EmployeeDocument.created_at.desc())
    )
    return result.scalars().all()


async def add_employee_document(
    tenant_id: UUID, employee_id: UUID, payload: EmployeeDocumentCreate, db: AsyncSession
) -> EmployeeDocument:
    emp = await get_employee(tenant_id, employee_id, db)

    doc = EmployeeDocument(
        tenant_id=tenant_id,
        employee_id=emp.id,
        document_type=payload.document_type,
        document_number=payload.document_number,
        issued_at=payload.issued_at,
        expiry_date=payload.expiry_date,
        notes=payload.notes,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


# ------------------------------------------------------------------
# Payroll Engine
# ------------------------------------------------------------------
async def generate_payroll(
    tenant_id: UUID,
    payload: PayrollGenerationRequest,
    actor_id: UUID | None,
    db: AsyncSession,
) -> list[PayrollSlip]:

    # 1. Obter a lista de empregados a processar
    if payload.employee_id:
        emps = [await get_employee(tenant_id, payload.employee_id, db)]
    else:
        result = await db.execute(
            select(Employee).where(Employee.tenant_id == tenant_id, Employee.status == "active")
        )
        emps = result.scalars().all()

    slips = []

    for emp in emps:
        # Check if slip already exists for this month/year
        stmt = select(PayrollSlip).where(
            PayrollSlip.tenant_id == tenant_id,
            PayrollSlip.employee_id == emp.id,
            PayrollSlip.period_month == payload.period_month,
            PayrollSlip.period_year == payload.period_year,
        )
        existing = await db.scalar(stmt)
        if existing:
            continue  # already generated

        # 2. Daily Value Mathematics
        daily_value = _decimal(emp.base_salary / Decimal("30"))
        lines = []

        # 2.1 Calculate Absences (Faltas Injustificadas)
        _, last_day = calendar.monthrange(payload.period_year, payload.period_month)
        start_dt = date(payload.period_year, payload.period_month, 1)
        end_dt = date(payload.period_year, payload.period_month, last_day)

        absences_stmt = select(Absence).where(
            Absence.tenant_id == tenant_id,
            Absence.employee_id == emp.id,
            Absence.is_paid.is_(False),
            Absence.start_date >= start_dt,
            Absence.start_date <= end_dt,
        )
        absences_result = await db.execute(absences_stmt)
        unpaid_absences = absences_result.scalars().all()

        days_absent = Decimal("0")
        for ab in unpaid_absences:
            # Simplistic calculation: count total days of absence inside this month
            delta = (ab.end_date - ab.start_date).days + 1
            days_absent += Decimal(str(delta))

        worked_days = Decimal("30") - days_absent
        if worked_days < 0:
            worked_days = Decimal("0")

        gross_salary = _decimal(worked_days * daily_value)
        total_taxable = gross_salary

        # 3. Earnings (R01)
        r01 = PayrollSlipLine(
            tenant_id=tenant_id,
            code="R01",
            description="REMUNERAÇÃO MENSAL (MZN)",
            quantity=worked_days,
            unit_price=daily_value,
            amount=gross_salary,
            irps_tax_percentage=emp.irps_tax_percentage,
            is_taxable_inss=True,
            is_taxable_syndicate=False,
        )
        lines.append(r01)

        # Variables (R02, R03, R04, R05)
        emp_vars = None
        if payload.variables:
            emp_vars = next((v for v in payload.variables if v.employee_id == emp.id), None)

        if emp_vars:
            if emp_vars.overtime_hours > 0:
                overtime_rate = _decimal((daily_value / Decimal("8")) * Decimal("1.5"))
                overtime_amount = _decimal(emp_vars.overtime_hours * overtime_rate)
                total_taxable += overtime_amount
                r02 = PayrollSlipLine(
                    tenant_id=tenant_id,
                    code="R02",
                    description="HORAS EXTRAORDINÁRIAS",
                    quantity=emp_vars.overtime_hours,
                    unit_price=overtime_rate,
                    amount=overtime_amount,
                    irps_tax_percentage=emp.irps_tax_percentage,
                    is_taxable_inss=True,
                    is_taxable_syndicate=False,
                )
                lines.append(r02)

            if emp_vars.meal_allowance_days > 0:
                meal_allowance_rate = Decimal("200.00")  # Exemplo fixo
                meal_amount = _decimal(emp_vars.meal_allowance_days * meal_allowance_rate)
                total_taxable += meal_amount
                r03 = PayrollSlipLine(
                    tenant_id=tenant_id,
                    code="R03",
                    description="SUBSÍDIO DE ALIMENTAÇÃO",
                    quantity=emp_vars.meal_allowance_days,
                    unit_price=meal_allowance_rate,
                    amount=meal_amount,
                    irps_tax_percentage=emp.irps_tax_percentage,
                    is_taxable_inss=True,
                    is_taxable_syndicate=False,
                )
                lines.append(r03)

            if emp_vars.other_allowances > 0:
                total_taxable += emp_vars.other_allowances
                r04 = PayrollSlipLine(
                    tenant_id=tenant_id,
                    code="R04",
                    description="OUTROS SUBSÍDIOS",
                    quantity=Decimal("1.00"),
                    unit_price=emp_vars.other_allowances,
                    amount=emp_vars.other_allowances,
                    irps_tax_percentage=emp.irps_tax_percentage,
                    is_taxable_inss=True,
                    is_taxable_syndicate=False,
                )
                lines.append(r04)

            if emp_vars.bonus > 0:
                total_taxable += emp_vars.bonus
                r05 = PayrollSlipLine(
                    tenant_id=tenant_id,
                    code="R05",
                    description="BÓNUS E PRÉMIOS",
                    quantity=Decimal("1.00"),
                    unit_price=emp_vars.bonus,
                    amount=emp_vars.bonus,
                    irps_tax_percentage=emp.irps_tax_percentage,
                    is_taxable_inss=True,
                    is_taxable_syndicate=False,
                )
                lines.append(r05)

        # Update gross salary to include all earnings
        gross_salary = total_taxable

        # 4. Deductions (D01: INSS 3%)
        inss_deduction = _decimal(total_taxable * Decimal("0.03"))
        d01 = PayrollSlipLine(
            tenant_id=tenant_id,
            code="D01",
            description="SEGURANÇA SOCIAL (3%)",
            quantity=Decimal("1.00"),
            unit_price=inss_deduction,
            amount=-inss_deduction,
            irps_tax_percentage=None,
            is_taxable_inss=False,
            is_taxable_syndicate=False,
        )
        lines.append(d01)

        # 5. Deductions (D02: IRPS)
        irps_deduction = (
            _decimal(total_taxable * (emp.irps_tax_percentage / Decimal("100")))
            if emp.irps_tax_percentage > 0
            else Decimal("0.00")
        )
        if irps_deduction > 0:
            d02 = PayrollSlipLine(
                tenant_id=tenant_id,
                code="D02",
                description=f"IRPS ({emp.irps_tax_percentage}%)",
                quantity=Decimal("1.00"),
                unit_price=irps_deduction,
                amount=-irps_deduction,
                irps_tax_percentage=None,
                is_taxable_inss=False,
                is_taxable_syndicate=False,
            )
            lines.append(d02)

        # 6. Deductions (D03: Adiantamentos/Vales)
        advances_stmt = select(SalaryAdvance).where(
            SalaryAdvance.tenant_id == tenant_id,
            SalaryAdvance.employee_id == emp.id,
            SalaryAdvance.status == "approved",
            # Qualquer adiantamento aprovado e ainda não deduzido entra neste processamento.
        )
        advances_result = await db.execute(advances_stmt)
        advances = advances_result.scalars().all()

        total_advances_deduction = Decimal("0")
        for advance in advances:
            total_advances_deduction += advance.amount
            advance.status = "deducted"  # Mark as deducted so it doesn't get deducted next month

        if total_advances_deduction > 0:
            d03 = PayrollSlipLine(
                tenant_id=tenant_id,
                code="D03",
                description="ADIANTAMENTOS DE VENCIMENTO",
                quantity=Decimal("1.00"),
                unit_price=total_advances_deduction,
                amount=-total_advances_deduction,
                irps_tax_percentage=None,
                is_taxable_inss=False,
                is_taxable_syndicate=False,
            )
            lines.append(d03)

        total_inss = inss_deduction
        total_irps = irps_deduction
        total_deductions = total_inss + total_irps + total_advances_deduction
        net_salary = gross_salary - total_deductions

        slip = PayrollSlip(
            tenant_id=tenant_id,
            employee_id=emp.id,
            period_month=payload.period_month,
            period_year=payload.period_year,
            gross_salary=gross_salary,
            total_inss=total_inss,
            total_irps=total_irps,
            total_syndicate=Decimal("0.00"),
            total_deductions=total_deductions,
            net_salary=net_salary,
            status="draft",
        )
        db.add(slip)
        await db.flush()  # get ID for lines

        for line in lines:
            line.payroll_slip_id = slip.id
            db.add(line)

        slips.append(slip)

    if slips:
        # PGC-NIRF: Aggregate for the Journal Entry
        total_gross = sum((s.gross_salary for s in slips), Decimal("0"))
        total_inss_employee = sum((s.total_inss for s in slips), Decimal("0"))
        total_inss_employer = total_gross * Decimal("0.04")  # 4% Patronal
        total_irps = sum((s.total_irps for s in slips), Decimal("0"))

        # We need to find total advances from lines to know how much to credit 42.2
        total_advances = sum(
            (abs(line.amount) for slip in slips for line in slip.lines if line.code == "D03"),
            Decimal("0"),
        )
        total_net = sum((s.net_salary for s in slips), Decimal("0"))

        if total_gross > 0:
            # Look up accounts
            async def get_account(code: str, name: str, act_type: str) -> str:
                res = await db.execute(
                    select(Account).where(Account.tenant_id == tenant_id, Account.code == code)
                )
                acc = res.scalars().first()
                if not acc:
                    acc = Account(tenant_id=tenant_id, code=code, name=name, account_type=act_type)
                    db.add(acc)
                    await db.flush()
                return str(acc.id)

            acc_622 = UUID(await get_account("6.2.2", "Remunerações dos trabalhadores", "Expense"))
            acc_623 = UUID(
                await get_account("6.2.3", "Encargos sobre remunerações (INSS)", "Expense")
            )
            acc_442 = UUID(
                await get_account("4.4.2", "Impostos retidos na fonte (IRPS)", "Liability")
            )
            acc_449 = UUID(await get_account("4.4.9", "Contribuições para o INSS", "Liability"))
            acc_4512 = UUID(
                await get_account("4.5.1.2", "Adiantamentos aos trabalhadores", "Asset")
            )
            acc_4622 = UUID(
                await get_account("4.6.2.2", "Remunerações a pagar aos trabalhadores", "Liability")
            )

            items = []
            if total_gross > 0:
                items.append(
                    JournalItemCreate(account_id=acc_622, debit=total_gross, credit=Decimal("0.00"))
                )
            if total_inss_employer > 0:
                items.append(
                    JournalItemCreate(
                        account_id=acc_623, debit=total_inss_employer, credit=Decimal("0.00")
                    )
                )

            if total_irps > 0:
                items.append(
                    JournalItemCreate(account_id=acc_442, debit=Decimal("0.00"), credit=total_irps)
                )
            if (total_inss_employee + total_inss_employer) > 0:
                items.append(
                    JournalItemCreate(
                        account_id=acc_449,
                        debit=Decimal("0.00"),
                        credit=(total_inss_employee + total_inss_employer),
                    )
                )
            if total_advances > 0:
                items.append(
                    JournalItemCreate(
                        account_id=acc_4512, debit=Decimal("0.00"), credit=total_advances
                    )
                )
            if total_net > 0:
                items.append(
                    JournalItemCreate(account_id=acc_4622, debit=Decimal("0.00"), credit=total_net)
                )

            entry_payload = JournalEntryCreate(
                journal_type="VENC",
                date=date(payload.period_year, payload.period_month, 1),
                reference=f"Processamento Salarial {payload.period_month}/{payload.period_year}",
                description=(
                    "Reconhecimento de salários e encargos do mês "
                    f"{payload.period_month}/{payload.period_year}"
                ),
                items=items,
            )
            await create_journal_entry(db, tenant_id, entry_payload)

        await db.commit()
        for slip in slips:
            await db.refresh(slip)

    return slips


async def list_payroll_slips(
    tenant_id: UUID, month: int, year: int, db: AsyncSession
) -> Sequence[PayrollSlip]:
    result = await db.execute(
        select(PayrollSlip).where(
            PayrollSlip.tenant_id == tenant_id,
            PayrollSlip.period_month == month,
            PayrollSlip.period_year == year,
        )
    )
    slips = result.scalars().all()

    # Eager load lines manually for now
    for slip in slips:
        lines_res = await db.execute(
            select(PayrollSlipLine).where(PayrollSlipLine.payroll_slip_id == slip.id)
        )
        slip.lines = list(lines_res.scalars().all())

    return slips
