from fpdf import FPDF

from app.modules.tenants.models import Tenant, TenantDocumentProfile


class BaseReportEngine(FPDF):
    """
    Motor central para a geração de PDFs em modo White-Label.
    Garante que todos os documentos gerados têm a formatação e identidade do Tenant.
    """

    def __init__(
        self, tenant: Tenant, profile: TenantDocumentProfile | None, title: str = "Documento"
    ):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.tenant = tenant
        self.profile = profile
        self.document_title = title

        # Cores corporativas base (Pode ser estendido para ler do profile no futuro)
        self.primary_color = (40, 40, 40)
        self.secondary_color = (100, 100, 100)
        self.accent_color = (200, 200, 200)

        # Metadados
        self.set_title(title)
        self.set_author(
            self.profile.legal_name
            if self.profile and self.profile.legal_name
            else self.tenant.name
        )

        # Add page (This automatically triggers header())
        self.set_auto_page_break(auto=True, margin=15)
        self.add_page()

    def header(self):
        # Fallback: Se não houver profile, usamos os dados base do Tenant
        company_name = self.tenant.name
        nuit = self.tenant.nuit or "Consumidor Final"
        address = ""
        contact = self.tenant.whatsapp_number or ""

        if self.profile:
            company_name = self.profile.legal_name or company_name
            address_parts = [
                self.profile.address_line1,
                self.profile.city,
                self.profile.province,
                self.profile.country,
            ]
            address = ", ".join([p for p in address_parts if p])
            if self.profile.phone:
                contact = self.profile.phone
            elif self.profile.email:
                contact = self.profile.email

        # Logo vs Nome Garrafal
        # Como não temos S3 ligado neste exacto passo, faremos o "Fallback Elegante"
        self.set_font("helvetica", "B", 18)
        self.set_text_color(*self.primary_color)
        self.cell(0, 10, company_name.upper(), border=0, new_x="LMARGIN", new_y="NEXT", align="L")

        self.set_font("helvetica", "", 10)
        self.set_text_color(*self.secondary_color)
        if address:
            self.cell(0, 5, address, border=0, new_x="LMARGIN", new_y="NEXT", align="L")
        self.cell(
            0,
            5,
            f"NUIT: {nuit} | Contacto: {contact}",
            border=0,
            new_x="LMARGIN",
            new_y="NEXT",
            align="L",
        )

        # Título do Documento à Direita
        self.set_y(15)
        self.set_font("helvetica", "B", 16)
        self.set_text_color(*self.primary_color)
        self.cell(
            0, 10, self.document_title.upper(), border=0, new_x="LMARGIN", new_y="NEXT", align="R"
        )

        # Linha separadora
        self.set_y(35)
        self.set_draw_color(*self.accent_color)
        self.line(10, 35, 200, 35)

        # Margem inferior para começar o conteúdo
        self.set_y(40)

    def footer(self):
        # Go to 1.5 cm from bottom
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(*self.secondary_color)

        footer_text = f"Gerado por {self.tenant.name} - Plataforma ROTAS"
        if self.profile and self.profile.invoice_footer:
            footer_text = self.profile.invoice_footer

        self.cell(0, 5, footer_text, align="L")
        self.set_x(10)
        self.cell(0, 5, f"Página {self.page_no()}/{{nb}}", align="R")

    def export_bytes(self) -> bytes:
        """Exporta o PDF renderizado como bytes para envio direto por API."""
        return bytes(self.output())
