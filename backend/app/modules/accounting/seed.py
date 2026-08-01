import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accounting.models import Account


async def seed_pgc_nirf(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """
    Semeia o Plano Geral de Contabilidade para Pequenas Empresas (PGC-PE - Moçambique)
    (Decreto n.º 70/2009) para um Tenant recém-criado.
    """
    # Verifica se já existem contas
    result = await session.execute(select(Account).where(Account.tenant_id == tenant_id).limit(1))
    if result.scalars().first():
        return  # Já tem plano de contas

    # Definir as contas base PGC-PE
    accounts_data = [
        # CLASSE 1 - MEIOS FINANCEIROS
        {"code": "1.1", "name": "Caixa", "type": "Asset"},
        {"code": "1.2", "name": "Bancos", "type": "Asset"},
        {"code": "1.3", "name": "Outros instrumentos financeiros", "type": "Asset"},
        # CLASSE 2 - INVENTÁRIOS E ACTIVOS BIOLÓGICOS
        {"code": "2.1", "name": "Compras", "type": "Asset"},
        {"code": "2.2", "name": "Mercadorias", "type": "Asset"},
        {"code": "2.6", "name": "Matérias primas, auxiliares e materiais", "type": "Asset"},
        # CLASSE 3 - INVESTIMENTOS DE CAPITAL
        {"code": "3.1", "name": "Investimentos financeiros", "type": "Asset"},
        {"code": "3.2", "name": "Activos tangíveis", "type": "Asset"},
        {"code": "3.3", "name": "Activos intangíveis", "type": "Asset"},
        # CLASSE 4 - CONTAS A RECEBER, CONTAS A PAGAR
        {"code": "4.1", "name": "Clientes", "type": "Asset"},
        {"code": "4.2", "name": "Fornecedores", "type": "Liability"},
        {"code": "4.3", "name": "Empréstimos obtidos", "type": "Liability"},
        {"code": "4.4", "name": "Estado", "type": "Liability"},
        {
            "code": "4.4.2",
            "name": "Impostos retidos na fonte (IRPS)",
            "type": "Liability",
            "parent_code": "4.4",
        },
        {
            "code": "4.4.3",
            "name": "Imposto sobre o valor acrescentado (IVA)",
            "type": "Liability",
            "parent_code": "4.4",
        },
        {
            "code": "4.4.9",
            "name": "Contribuições para o INSS",
            "type": "Liability",
            "parent_code": "4.4",
        },
        {"code": "4.5", "name": "Outros devedores", "type": "Asset"},
        {"code": "4.5.1", "name": "Pessoal (Devedor)", "type": "Asset", "parent_code": "4.5"},
        {
            "code": "4.5.1.2",
            "name": "Adiantamentos aos trabalhadores",
            "type": "Asset",
            "parent_code": "4.5.1",
        },
        {"code": "4.6", "name": "Outros credores", "type": "Liability"},
        {"code": "4.6.2", "name": "Pessoal (Credor)", "type": "Liability", "parent_code": "4.6"},
        {
            "code": "4.6.2.2",
            "name": "Remunerações a pagar aos trabalhadores",
            "type": "Liability",
            "parent_code": "4.6.2",
        },
        # CLASSE 5 - CAPITAL PRÓPRIO
        {"code": "5.1", "name": "Capital", "type": "Equity"},
        {"code": "5.5", "name": "Reservas", "type": "Equity"},
        {"code": "5.9", "name": "Resultados transitados", "type": "Equity"},
        # CLASSE 6 - GASTOS E PERDAS
        {"code": "6.1", "name": "Custo dos inventários", "type": "Expense"},
        {"code": "6.2", "name": "Gastos com o pessoal", "type": "Expense"},
        {
            "code": "6.2.2",
            "name": "Remunerações dos trabalhadores",
            "type": "Expense",
            "parent_code": "6.2",
        },
        {
            "code": "6.2.3",
            "name": "Encargos sobre remunerações (INSS)",
            "type": "Expense",
            "parent_code": "6.2",
        },
        {"code": "6.3", "name": "Fornecimentos e serviços de terceiros", "type": "Expense"},
        {"code": "6.5", "name": "Amortizações do período", "type": "Expense"},
        {"code": "6.9", "name": "Gastos e perdas financeiros", "type": "Expense"},
        # CLASSE 7 - RENDIMENTOS E GANHOS
        {"code": "7.1", "name": "Vendas", "type": "Revenue"},
        {"code": "7.2", "name": "Prestação de serviços", "type": "Revenue"},
        {"code": "7.8", "name": "Rendimentos e ganhos financeiros", "type": "Revenue"},
        # CLASSE 8 - RESULTADOS
        {"code": "8.1", "name": "Resultados operacionais", "type": "Equity"},
        {"code": "8.8", "name": "Resultado líquido do período", "type": "Equity"},
    ]

    # Armazenar instâncias criadas para resolver parent_id
    created_accounts = {}

    for data in accounts_data:
        parent_id = None
        if "parent_code" in data:
            parent_id = created_accounts[data["parent_code"]].id

        acc = Account(
            tenant_id=tenant_id,
            code=data["code"],
            name=data["name"],
            account_type=data["type"],
            parent_id=parent_id,
        )
        session.add(acc)
        # Flush para obter o ID e permitir self-referencing
        await session.flush()
        created_accounts[data["code"]] = acc

    await session.commit()
