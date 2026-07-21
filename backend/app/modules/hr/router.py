from typing import Annotated, List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, get_current_principal
from app.core.deps import get_session
from app.core.rbac import require_permission, HR_READ, HR_WRITE, HR_PAYROLL_GENERATE, HR_PAYROLL_APPROVE
from app.modules.hr import schemas, service

# Em produção real teríamos permissões específicas para RH, mas para já utilizamos WORKSHOP_WRITE ou similar, 
# ou podemos omitir validações extremas de escopo num MVP (aqui uso 'require_permission("tenant_admin")' ou apenas Principal validado)

router = APIRouter(prefix="/hr", tags=["hr"])

PrincipalDep = Annotated[Principal, Depends(get_current_principal)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Aqui assumimos que apenas um utilizador logado de uma Tenant pode aceder:
@router.get("/employees", response_model=List[schemas.EmployeeResponse])
async def list_employees(
    principal: Annotated[Principal, Depends(require_permission(HR_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_employees(principal.tenant_id, db)


@router.post("/employees", response_model=schemas.EmployeeResponse, status_code=201)
async def create_employee(
    payload: schemas.EmployeeCreate,
    principal: Annotated[Principal, Depends(require_permission(HR_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.create_employee(principal.tenant_id, payload, db)


@router.get("/employees/{employee_id}/documents", response_model=List[schemas.EmployeeDocumentResponse])
async def list_employee_documents(
    employee_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(HR_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_employee_documents(principal.tenant_id, employee_id, db)


@router.post("/employees/{employee_id}/documents", response_model=schemas.EmployeeDocumentResponse, status_code=201)
async def add_employee_document(
    employee_id: UUID,
    payload: schemas.EmployeeDocumentCreate,
    principal: Annotated[Principal, Depends(require_permission(HR_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.add_employee_document(principal.tenant_id, employee_id, payload, db)


@router.post("/payroll/generate", response_model=List[schemas.PayrollSlipResponse], status_code=201)
async def generate_payroll(
    payload: schemas.PayrollGenerationRequest,
    principal: Annotated[Principal, Depends(require_permission(HR_PAYROLL_GENERATE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.generate_payroll(principal.tenant_id, payload, principal.user_id, db)


@router.get("/payroll", response_model=List[schemas.PayrollSlipResponse])
async def list_payroll_slips(
    month: int,
    year: int,
    principal: Annotated[Principal, Depends(require_permission(HR_READ))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await service.list_payroll_slips(principal.tenant_id, month, year, db)


# ---------------------------------------------------------
# Salary Advances (Vales)
# ---------------------------------------------------------

@router.get("/advances", response_model=List[schemas.SalaryAdvanceResponse])
async def list_salary_advances(
    principal: PrincipalDep,
    db: SessionDep,
):
    from sqlalchemy import select
    from app.modules.hr.models import SalaryAdvance
    stmt = select(SalaryAdvance).where(SalaryAdvance.tenant_id == principal.tenant_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/advances", response_model=schemas.SalaryAdvanceResponse, status_code=201)
async def create_salary_advance(
    payload: schemas.SalaryAdvanceCreate,
    principal: Annotated[Principal, Depends(require_permission(HR_WRITE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    from app.modules.hr.models import SalaryAdvance
    advance = SalaryAdvance(
        tenant_id=principal.tenant_id,
        **payload.model_dump()
    )
    db.add(advance)
    await db.commit()
    await db.refresh(advance)
    return advance


@router.patch("/advances/{advance_id}/approve", response_model=schemas.SalaryAdvanceResponse)
async def approve_salary_advance(
    advance_id: UUID,
    principal: Annotated[Principal, Depends(require_permission(HR_PAYROLL_APPROVE))],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    from sqlalchemy import select
    from fastapi import HTTPException
    from app.modules.hr.models import SalaryAdvance
    stmt = select(SalaryAdvance).where(
        SalaryAdvance.tenant_id == principal.tenant_id,
        SalaryAdvance.id == advance_id
    )
    advance = await db.scalar(stmt)
    if not advance:
        raise HTTPException(status_code=404, detail="Advance not found")
        
    advance.status = "approved"
    await db.commit()
    await db.refresh(advance)
    return advance


# ---------------------------------------------------------
# PS2 / Bank Transfers Export
# ---------------------------------------------------------
@router.get("/payroll/export-ps2")
async def export_ps2_file(
    month: int,
    year: int,
    principal: PrincipalDep,
    db: SessionDep,
):
    """
    Gera um ficheiro CSV limpo com NOME, NIB e VALOR LÍQUIDO 
    pronto a carregar no banco ou formato semelhante.
    """
    from sqlalchemy import select
    from fastapi.responses import PlainTextResponse
    from app.modules.hr.models import PayrollSlip, Employee
    
    stmt = select(PayrollSlip, Employee).join(Employee, PayrollSlip.employee_id == Employee.id).where(
        PayrollSlip.tenant_id == principal.tenant_id,
        PayrollSlip.period_month == month,
        PayrollSlip.period_year == year
    )
    result = await db.execute(stmt)
    rows = result.all()
    
    csv_lines = ["NOME,NIB,VALOR_LIQUIDO"]
    for slip, emp in rows:
        nib = emp.bank_account_nib or "000000000000000000000"
        csv_lines.append(f"{emp.first_name} {emp.last_name},{nib},{slip.net_salary}")
        
    csv_content = "\n".join(csv_lines)
    
    return PlainTextResponse(
        content=csv_content,
        headers={
            "Content-Disposition": f"attachment; filename=vencimentos_{year}_{month:02d}.csv"
        }
    )
