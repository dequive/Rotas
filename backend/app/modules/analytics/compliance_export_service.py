"""ANA-03: Compliance expiry PDF report using fpdf2.

Two sections:
  1. Documentos Vencidos  — expired as of today
  2. A vencer em 30 dias  — expiring within the next 30 days

Uses DejaVuSans (same font path as billing exporters) for full UTF-8 / Portuguese support.
Falls back to built-in Helvetica if the font file is not present.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Same font directory used by billing exporters
_FONTS_DIR = Path(__file__).parent.parent / "billing" / "fonts"
_DEJAVU_REGULAR = _FONTS_DIR / "DejaVuSans.ttf"
_DEJAVU_BOLD = _FONTS_DIR / "DejaVuSans-Bold.ttf"


async def generate_compliance_report_pdf(
    db: AsyncSession,
    tenant_id: UUID,
) -> bytes:
    """ANA-03: Compliance PDF with two sections: Vencidos and A vencer em 30 dias.

    Queries the analytics service for document expiry alerts (horizon = 60 days so we
    capture both expired docs and those expiring within 30 days in a single pass).
    """
    from app.modules.analytics.service import get_document_expiry_alerts
    from app.modules.tenants.models import Tenant

    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    tenant_name = tenant.name if tenant else "ROTAS"

    # horizon=60 so we get expired (days_remaining < 0) + expiring within 30 days
    all_alerts = await get_document_expiry_alerts(db, tenant_id, horizon_days=60)

    expired = [a for a in all_alerts if a["days_remaining"] < 0]
    expiring_30 = [a for a in all_alerts if 0 <= a["days_remaining"] <= 30]

    today_str = datetime.now(UTC).date().strftime("%d/%m/%Y")

    use_dejavu = _DEJAVU_REGULAR.exists() and _DEJAVU_BOLD.exists()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    if use_dejavu:
        pdf.add_font("DejaVu", "", str(_DEJAVU_REGULAR))
        pdf.add_font("DejaVu", "B", str(_DEJAVU_BOLD))
        font_family = "DejaVu"
    else:
        font_family = "Helvetica"

    def _set(style: str = "", size: int = 10) -> None:
        pdf.set_font(font_family, style=style, size=size)

    # ── Document header ──────────────────────────────────────────────────────
    _set("B", 14)
    pdf.cell(
        0, 10, f"Relatório de Conformidade — {tenant_name}",
        new_x="LMARGIN", new_y="NEXT", align="C",
    )
    _set("", 9)
    pdf.cell(0, 6, f"Gerado em: {today_str}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(6)

    # ── Section renderer ─────────────────────────────────────────────────────
    def _write_section(title: str, items: list[dict]) -> None:
        _set("B", 10)
        pdf.set_fill_color(230, 230, 230)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT", fill=True)

        if not items:
            _set("", 9)
            pdf.cell(0, 6, "  Nenhum documento nesta categoria.", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
            return

        # Table header row
        _set("B", 8)
        pdf.cell(35, 6, "Tipo", border=1)
        pdf.cell(55, 6, "Entidade", border=1)
        pdf.cell(50, 6, "Documento", border=1)
        pdf.cell(30, 6, "Vence em", border=1)
        pdf.cell(20, 6, "Dias", border=1, new_x="LMARGIN", new_y="NEXT")

        _set("", 8)
        for item in items:
            pdf.cell(35, 6, str(item.get("entity_type", ""))[:12], border=1)
            pdf.cell(55, 6, str(item.get("entity_name", ""))[:26], border=1)
            pdf.cell(50, 6, str(item.get("document_type", ""))[:24], border=1)
            pdf.cell(30, 6, str(item.get("expires_at", ""))[:10], border=1)
            pdf.cell(
                20, 6, str(item.get("days_remaining", "")),
                border=1, new_x="LMARGIN", new_y="NEXT",
            )

        pdf.ln(4)

    _write_section("Documentos Vencidos", expired)
    _write_section("A vencer em 30 dias", expiring_30)

    return bytes(pdf.output())
