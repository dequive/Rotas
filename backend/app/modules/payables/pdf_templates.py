# Para termos tipagem do third_party (vamos assumir que a model ThirdParty tem campos como name e tax_id)
from typing import Any

from app.core.pdf_engine import BaseReportEngine
from app.modules.payables.models import PurchaseOrder


class PurchaseOrderPDF(BaseReportEngine):
    """
    Template profissional para emissão de Requisições de Compra.
    Gera um PDF White-Label que será enviado ao Fornecedor.
    """

    def __init__(self, tenant, profile, purchase_order: PurchaseOrder, third_party: Any):
        # Inicia o motor, que gera automaticamente o cabeçalho White-Label do Tenant
        super().__init__(tenant, profile, title="Requisição de Compra")
        self.po = purchase_order
        self.supplier = third_party
        self.build_document()

    def build_document(self):
        # 1. Bloco do Fornecedor (Entidade de Destino)
        self.set_y(45)
        self.set_font("helvetica", "B", 12)
        self.set_text_color(*self.primary_color)
        self.cell(0, 8, "DADOS DO FORNECEDOR", new_x="LMARGIN", new_y="NEXT")

        self.set_font("helvetica", "", 10)
        self.cell(40, 6, "Entidade:", border=0)
        self.set_font("helvetica", "B", 10)
        self.cell(0, 6, self.supplier.name, border=0, new_x="LMARGIN", new_y="NEXT")

        self.set_font("helvetica", "", 10)
        self.cell(40, 6, "NUIT / Tax ID:", border=0)
        self.cell(0, 6, getattr(self.supplier, "tax_id", "N/A") or "N/A", border=0, new_x="LMARGIN", new_y="NEXT")

        # 2. Informações da Requisição
        self.set_y(45)
        self.set_x(120)
        self.set_font("helvetica", "B", 10)
        self.cell(40, 6, "Nº Requisição:")
        self.set_font("helvetica", "", 10)
        self.cell(0, 6, self.po.po_number, new_x="LMARGIN", new_y="NEXT")

        self.set_x(120)
        self.set_font("helvetica", "B", 10)
        self.cell(40, 6, "Data de Emissão:")
        self.set_font("helvetica", "", 10)
        issued_date = self.po.issued_at.strftime("%d/%m/%Y") if self.po.issued_at else "N/A"
        self.cell(0, 6, issued_date, new_x="LMARGIN", new_y="NEXT")

        # Linha de separação
        self.set_y(80)
        self.set_draw_color(*self.accent_color)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_y(85)

        # 3. Tabela de Pedido
        self.set_font("helvetica", "B", 10)
        self.set_fill_color(240, 240, 240)

        # Cabeçalhos da Tabela
        self.cell(140, 10, " Descrição do Pedido / Serviço", border=1, fill=True)
        self.cell(50, 10, " Valor Estimado", border=1, fill=True, align="R", new_x="LMARGIN", new_y="NEXT")

        # Conteúdo
        self.set_font("helvetica", "", 10)
        # Multi_cell para a descrição no caso de ter muitas linhas
        start_y = self.get_y()
        start_x = self.get_x()

        self.multi_cell(140, 8, f" {self.po.description}", border=1)

        end_y = self.get_y()
        self.set_xy(start_x + 140, start_y)

        # O Valor estimado
        amount_str = (
            f"{float(self.po.estimated_amount):,.2f} {self.po.currency}" if self.po.estimated_amount else "Sob Consulta"
        )
        self.cell(50, end_y - start_y, amount_str, border=1, align="R", new_x="LMARGIN", new_y="NEXT")

        self.set_y(end_y + 10)

        # 4. Termos e Condições (Opcional, dá um toque altamente profissional)
        self.set_font("helvetica", "B", 9)
        self.cell(0, 6, "Condições da Requisição:", new_x="LMARGIN", new_y="NEXT")
        self.set_font("helvetica", "", 8)
        self.set_text_color(*self.secondary_color)
        termos = (
            "1. A presente requisição serve apenas como intenção de compra e não constitui fatura.\n"
            "2. Todas as faturas emitidas devem fazer referência ao Nº desta Requisição.\n"
            "3. Caso o valor real exceda a estimativa em mais de 10%, é necessária aprovação prévia."
        )
        self.multi_cell(0, 5, termos)


def generate_purchase_order_pdf(tenant, profile, po, supplier) -> bytes:
    """Função Helper para inicializar e exportar a Requisição."""
    pdf = PurchaseOrderPDF(tenant, profile, po, supplier)
    return pdf.export_bytes()
