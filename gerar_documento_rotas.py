from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor


OUT = Path(__file__).with_name("ROTAS_Engenharia_v1.1.docx")

BLUE_DARK = "1A3A5C"
BLUE_MID = "2563EB"
BLUE_LIGHT = "DBEAFE"
ORANGE = "EA580C"
GRAY_LIGHT = "F1F5F9"
GRAY_MED = "CBD5E1"
GRAY_TEXT = "64748B"
WHITE = "FFFFFF"
BLACK = "111827"


def rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color)


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for m, v in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{m}"))
        if node is None:
            node = OxmlElement(f"w:{m}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(v))
        node.set(qn("w:type"), "dxa")


def set_table_borders(table, color=GRAY_MED, size="6") -> None:
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    borders = tbl_pr.first_child_found_in("w:tblBorders")
    if borders is None:
        borders = OxmlElement("w:tblBorders")
        tbl_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = f"w:{edge}"
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def set_table_width(table, widths_inches) -> None:
    table.autofit = False
    for row in table.rows:
        for idx, width in enumerate(widths_inches):
            if idx < len(row.cells):
                row.cells[idx].width = Inches(width)


def set_repeat_table_header(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)


def style_document(doc: Document) -> None:
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(1.8)
    section.bottom_margin = Cm(1.8)
    section.left_margin = Cm(1.9)
    section.right_margin = Cm(1.9)
    section.header_distance = Cm(0.9)
    section.footer_distance = Cm(0.9)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Arial"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
    normal.font.size = Pt(10.5)
    normal.font.color.rgb = rgb(BLACK)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.line_spacing = 1.15

    for name, size, color, before, after in [
        ("Heading 1", 18, BLUE_DARK, 16, 8),
        ("Heading 2", 14, BLUE_MID, 12, 6),
        ("Heading 3", 12, ORANGE, 8, 4),
    ]:
        st = styles[name]
        st.font.name = "Arial"
        st._element.rPr.rFonts.set(qn("w:eastAsia"), "Arial")
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = rgb(color)
        st.paragraph_format.space_before = Pt(before)
        st.paragraph_format.space_after = Pt(after)
        st.paragraph_format.keep_with_next = True


def add_header_footer(doc: Document) -> None:
    section = doc.sections[-1]
    header_p = section.header.paragraphs[0]
    header_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    run = header_p.add_run("ROTAS - Documentacao de Engenharia")
    run.font.name = "Arial"
    run.font.size = Pt(8.5)
    run.font.color.rgb = rgb(GRAY_TEXT)

    footer_p = section.footer.paragraphs[0]
    footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_p.add_run("Confidencial - Versao 1.1 - 2026")
    run.font.name = "Arial"
    run.font.size = Pt(8.5)
    run.font.color.rgb = rgb(GRAY_TEXT)


def p(doc, text="", bold=False, color=BLACK, size=10.5, align=None):
    paragraph = doc.add_paragraph()
    if align:
        paragraph.alignment = align
    paragraph.paragraph_format.space_after = Pt(6)
    paragraph.paragraph_format.line_spacing = 1.15
    run = paragraph.add_run(text)
    run.font.name = "Arial"
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = rgb(color)
    return paragraph


def bullet(doc, text: str, level: int = 0, bold_prefix: str | None = None):
    paragraph = doc.add_paragraph(style="List Bullet" if level == 0 else "List Bullet 2")
    paragraph.paragraph_format.space_after = Pt(4)
    paragraph.paragraph_format.line_spacing = 1.15
    if bold_prefix and text.startswith(bold_prefix):
        run = paragraph.add_run(bold_prefix)
        run.bold = True
        run.font.name = "Arial"
        run.font.size = Pt(10.5)
        paragraph.add_run(text[len(bold_prefix) :])
    else:
        run = paragraph.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(10.5)
    return paragraph


def h(doc, level: int, text: str):
    doc.add_heading(text, level=level)


def table(doc, headers, rows, widths, font_size=9.2):
    tbl = doc.add_table(rows=1, cols=len(headers))
    tbl.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_table_borders(tbl)
    set_table_width(tbl, widths)
    header = tbl.rows[0]
    set_repeat_table_header(header)
    for idx, label in enumerate(headers):
        cell = header.cells[idx]
        set_cell_shading(cell, BLUE_DARK)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        pr = cell.paragraphs[0]
        pr.paragraph_format.space_after = Pt(0)
        r = pr.add_run(label)
        r.bold = True
        r.font.name = "Arial"
        r.font.size = Pt(font_size)
        r.font.color.rgb = rgb(WHITE)
    for ridx, row in enumerate(rows):
        cells = tbl.add_row().cells
        for cidx, value in enumerate(row):
            cell = cells[cidx]
            set_cell_shading(cell, WHITE if ridx % 2 == 0 else GRAY_LIGHT)
            set_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            pr = cell.paragraphs[0]
            pr.paragraph_format.space_after = Pt(0)
            pr.paragraph_format.line_spacing = 1.08
            r = pr.add_run(str(value))
            r.font.name = "Arial"
            r.font.size = Pt(font_size)
            r.font.color.rgb = rgb(BLACK)
    doc.add_paragraph()
    return tbl


def callout(doc, title, text, fill=BLUE_LIGHT):
    tbl = doc.add_table(rows=1, cols=1)
    set_table_borders(tbl, color=fill, size="4")
    cell = tbl.cell(0, 0)
    set_cell_shading(cell, fill)
    set_cell_margins(cell, top=160, bottom=160, start=180, end=180)
    pr = cell.paragraphs[0]
    pr.paragraph_format.space_after = Pt(3)
    r = pr.add_run(title)
    r.bold = True
    r.font.name = "Arial"
    r.font.size = Pt(10.5)
    r.font.color.rgb = rgb(BLUE_DARK)
    pr2 = cell.add_paragraph()
    pr2.paragraph_format.space_after = Pt(0)
    r2 = pr2.add_run(text)
    r2.font.name = "Arial"
    r2.font.size = Pt(10)
    r2.font.color.rgb = rgb(BLACK)
    doc.add_paragraph()


def cover(doc):
    for _ in range(5):
        doc.add_paragraph()
    title = p(doc, "ROTAS", bold=True, color=BLUE_DARK, size=46, align=WD_ALIGN_PARAGRAPH.CENTER)
    title.paragraph_format.space_after = Pt(8)
    p(doc, "Plataforma de Gestao Total de Frotas", color=BLUE_MID, size=16, align=WD_ALIGN_PARAGRAPH.CENTER)
    p(doc, "Documentacao de Engenharia Completa", color=ORANGE, size=13, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_paragraph()
    callout(
        doc,
        "Proposta central",
        "Tudo o que acontece com a frota deve ficar registado, controlado, auditavel e disponivel mesmo em ambientes de baixa conectividade.",
    )
    p(doc, "Versao 1.1 | Mocambique | 2026", color=GRAY_TEXT, size=10, align=WD_ALIGN_PARAGRAPH.CENTER)
    p(doc, "Confidencial - Uso Interno", color=GRAY_TEXT, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)
    doc.add_page_break()


def toc(doc):
    h(doc, 1, "Indice Executivo")
    items = [
        "1. Visao geral e arquitectura de sistema",
        "2. Stack tecnico recomendado",
        "3. Modelo de dados e multi-tenancy",
        "4. Modulos operacionais",
        "5. API e endpoints",
        "6. App motorista offline-first",
        "7. Alertas e comunicacao",
        "8. Seguranca, auditoria e conformidade",
        "9. Custos, financeiro e modelo de negocio",
        "10. Roadmap, backlog e definition of done",
        "11. Deploy, observabilidade e operacao",
        "12. Riscos e proximos passos",
    ]
    for item in items:
        p(doc, item)
    doc.add_page_break()


def section_architecture(doc):
    h(doc, 1, "1. Visao Geral e Arquitectura de Sistema")
    p(
        doc,
        "O ROTAS e uma plataforma SaaS para gestao operacional, documental, financeira e auditavel de frotas, desenhada para operadores mocambicanos desde uma unica viatura ate frotas corporativas.",
    )
    callout(
        doc,
        "Diferencial competitivo",
        "A plataforma nasce mobile-first e offline-first, com WhatsApp como canal operacional principal, em vez de assumir internet estavel, desktop permanente e grandes equipas administrativas.",
    )
    table(
        doc,
        ["Principio", "Aplicacao no ROTAS", "Justificacao"],
        [
            ["Modularidade", "Modulos activaveis por plano e por maturidade do cliente", "Permite vender desde plano Solo ate Enterprise"],
            ["Offline-first", "PWA do motorista guarda dados localmente e sincroniza depois", "Conectividade 2G/3G instavel em rotas nacionais"],
            ["Multi-tenant", "Todas as entidades possuem tenant_id e isolamento de permissao", "Um unico produto serve varias empresas"],
            ["Event-driven", "Alertas disparados por eventos: checklist, abastecimento, documento, viagem", "Gestor recebe excepcao, nao ruido"],
            ["Auditabilidade", "Registos com timestamp, user_id, fotos, GPS e historico", "Prova operacional e reducao de fraude"],
            ["Mobile-first", "Fluxos curtos, botoes grandes, camera e GPS", "Motoristas usam smartphones Android simples"],
        ],
        [1.45, 2.55, 2.4],
    )
    h(doc, 2, "1.1 Camadas do sistema")
    for item in [
        "Apresentacao: dashboard gestor em Next.js, PWA motorista em React/Vite e notificacoes WhatsApp.",
        "API: FastAPI com autenticacao JWT, autorizacao por role, validacao Pydantic e rate limiting por tenant.",
        "Servicos: viaturas, checklists, combustivel, viagens, manutencao, acessorios, motoristas, financeiro e alertas.",
        "Dados: PostgreSQL/Supabase, Redis, IndexedDB local, Cloudflare R2 para fotos e documentos.",
    ]:
        bullet(doc, item)
    h(doc, 2, "1.2 Recomendacao arquitectural para MVP")
    p(
        doc,
        "Apesar da visao poder evoluir para microservicos, o MVP deve ser um monolito modular FastAPI. Isto reduz complexidade operacional e mantem fronteiras internas claras para futura extraccao.",
    )


def section_stack(doc):
    h(doc, 1, "2. Stack Tecnico Recomendado")
    table(
        doc,
        ["Camada", "Tecnologia", "Motivo"],
        [
            ["Backend API", "FastAPI + Python", "Performance, validacao forte, OpenAPI automatico e async nativo"],
            ["ORM/Migracoes", "SQLAlchemy 2.0 async + Alembic", "Modelagem robusta, migracoes versionadas"],
            ["Base de dados", "PostgreSQL via Supabase", "Managed PostgreSQL, RLS, PostGIS e real-time"],
            ["Cache/filas", "Redis ou Upstash", "Rate limit, jobs leves, cache e eventos"],
            ["Dashboard", "Next.js 14 + TypeScript", "Server Components, boa performance e deploy simples"],
            ["UI", "Tailwind + shadcn/ui", "Componentes acessiveis e rapidamente personalizaveis"],
            ["App motorista", "PWA React/Vite", "Sem app stores, offline-first e baixo atrito"],
            ["Offline local", "IndexedDB + Dexie.js", "Persistencia no browser com fila de sincronizacao"],
            ["Ficheiros", "Cloudflare R2", "API S3, baixo custo e sem egress fees"],
            ["Notificacoes", "WhatsApp Cloud API", "Canal ja usado por motoristas e gestores"],
            ["Pagamentos", "M-Pesa, e-Mola, transferencia", "Adequado ao mercado mocambicano"],
        ],
        [1.45, 2.05, 2.9],
    )
    h(doc, 2, "2.1 Estrutura recomendada do backend")
    for line in [
        "backend/app/main.py - entrada FastAPI",
        "backend/app/config.py - configuracao por ambiente",
        "backend/app/database.py - sessoes SQLAlchemy",
        "backend/app/modules/<modulo>/models.py - modelos ORM",
        "backend/app/modules/<modulo>/schemas.py - contratos Pydantic",
        "backend/app/modules/<modulo>/router.py - endpoints REST",
        "backend/app/modules/<modulo>/service.py - regras de negocio",
        "backend/app/tasks - jobs, alertas, relatorios e sync",
        "backend/tests - testes unitarios e integracao",
    ]:
        bullet(doc, line)
    h(doc, 2, "2.2 Decisoes de tecnologia")
    p(doc, "A prioridade tecnica deve ser confiabilidade, simplicidade operacional e custo baixo. Evitar dependencias complexas antes do MVP validar uso real.")


def section_data(doc):
    h(doc, 1, "3. Modelo de Dados e Multi-Tenancy")
    h(doc, 2, "3.1 Estrategia multi-tenant")
    p(
        doc,
        "No MVP, usar tenant_id em todas as tabelas e resolver o tenant a partir do token. RLS no PostgreSQL deve ser activado como camada adicional de defesa quando os fluxos principais estiverem estabilizados.",
    )
    table(
        doc,
        ["Entidade", "Responsabilidade", "Regras criticas"],
        [
            ["tenants", "Empresa/frota cliente", "Plano, limites, estado activo, contacto WhatsApp"],
            ["users", "Utilizadores do dashboard", "Role, tenant, password hash, estado activo"],
            ["drivers", "Motoristas e equipa operacional", "Carta, INATTER, score, viaturas autorizadas"],
            ["vehicles", "Ficha central da viatura", "Matricula unica por tenant, documentos, estado, QR"],
            ["checklist_templates", "Modelos dinamicos", "Itens bloqueantes, foto obrigatoria, categoria"],
            ["checklists", "Execucoes reais", "GPS, assinatura, respostas JSONB, estado final"],
            ["fuel_logs", "Abastecimentos", "Km crescente, recibo, consumo calculado, anomalias"],
            ["trips", "Viagens", "Origem/destino, carga, km, custos, entrega"],
            ["maintenance_records", "Historico tecnico", "OS, pecas, custos, bloqueio, downtime"],
            ["alerts", "Notificacoes e eventos", "Prioridade, canal, estado, entidade relacionada"],
            ["files", "Fotos e documentos", "Storage key, hash, entidade ligada, tenant"],
            ["audit_logs", "Trilha de auditoria", "Antes/depois, user, IP, acao, timestamp"],
        ],
        [1.75, 2.25, 2.4],
    )
    h(doc, 2, "3.2 Regras de modelagem")
    for item in [
        "Todas as tabelas operacionais devem ter tenant_id, created_at e, quando aplicavel, updated_at.",
        "Registos operacionais devem ser arquivados ou anulados, nao apagados fisicamente.",
        "Fotos e documentos devem ficar em R2; a base guarda metadados e storage_key.",
        "Campos flexiveis como respostas de checklist podem usar JSONB, mas relatorios criticos devem ter colunas normalizadas.",
        "Indices compostos por tenant_id e entidade principal sao obrigatorios para performance.",
    ]:
        bullet(doc, item)


def section_modules(doc):
    h(doc, 1, "4. Modulos Operacionais")
    modules = [
        ("Modulo 1 - Viaturas & Inventario", [
            "Ficha completa por viatura: marca, modelo, ano, matricula, chassi, cor e categoria.",
            "Documentos digitais: seguro, INATTER, licenca, DUA e carta de porte.",
            "Alertas de validade 30, 15 e 7 dias antes.",
            "QR Code por viatura para abrir checklist correcto.",
            "Historico de proprietario, operador, estado visual e acessorios vinculados.",
        ]),
        ("Modulo 2 - Checklists Operacionais", [
            "Tipos: pre-partida, chegada, carregamento, entrega, baldeacao, pernoite, semanal e mensal.",
            "Itens dinamicos por categoria de viatura.",
            "Foto obrigatoria por item critico, GPS automatico e assinatura digital.",
            "Itens bloqueantes impedem saida da viatura.",
            "Funciona offline e sincroniza depois.",
        ]),
        ("Modulo 3 - Combustivel", [
            "Registo de data, hora, posto, litros, valor, km, recibo e motorista.",
            "Calculo automatico de L/100km e custo por km.",
            "Alerta de consumo acima da media historica.",
            "Limite diario por viatura e comparativo entre postos.",
            "Relatorios por viatura, motorista, rota e periodo.",
        ]),
        ("Modulo 4 - Rotas & Viagens", [
            "Abertura de viagem com origem, destino, motorista, carga, km inicial e documento.",
            "Paragens: abastecimento, refeicao, avaria, fiscalizacao, pernoite.",
            "Portagens e travessias: ponte, barcaca, taxas e recibos.",
            "Fecho com km final, estado da carga, assinatura ou codigo de entrega.",
            "Relatorio de custo total por viagem.",
        ]),
        ("Modulo 5 - Manutencao", [
            "Planos preventivos por km, dias ou o que vier primeiro.",
            "Alertas 500km, 200km e no prazo.",
            "Correctiva com ordem de servico, pecas, oficina, custos e fotos.",
            "Bloqueio operacional da viatura ate aprovacao.",
            "Sub-modulo de pneus com posicao, vida util, rotacao e recauchutagem.",
        ]),
        ("Modulo 6 - Acessorios & Equipamentos", [
            "Inventario por viatura: triangulo, extintor, macaco, kit medico, lona, correntes, lacres.",
            "Estado: OK, danificado, em falta, emprestado, em reparacao.",
            "Verificacao em checklist de partida e chegada.",
            "Saida/devolucao com responsavel e alerta de atraso.",
            "Equipamentos especiais: reefer, grua, cisterna e GPS hardware.",
        ]),
        ("Modulo 7 - Motoristas & Equipa", [
            "Ficha pessoal, contacto de emergencia, carta, INATTER e INSS.",
            "Tipo: efectivo, prestador ou eventual.",
            "Viaturas autorizadas a conduzir.",
            "Score 0-100 baseado em checklists, incidentes, consumo, pontualidade e km sem ocorrencias.",
            "Historico de multas, acidentes e desempenho.",
        ]),
        ("Modulo 8 - Custos & Financeiro", [
            "Centros de custo por viatura: combustivel, manutencao, pneus, portagens, seguros, multas e despesas.",
            "Dashboard com custo total mensal, custo/km, viatura mais cara e comparativo mensal.",
            "Projecao de custos dos proximos 3 meses.",
            "Exportacao PDF/Excel por viatura, motorista e periodo.",
            "Base para decisao de substituicao ou abate.",
        ]),
        ("Modulo 9 - Alertas & Comunicacao", [
            "Canal principal: WhatsApp Cloud API.",
            "Alertas: checklist em atraso, item bloqueante, consumo anormal, documento vencendo, manutencao, incidente e viagem atrasada.",
            "Centro de notificacoes no dashboard com prioridade.",
            "Historico de alertas por entidade.",
            "Configuracao por tenant para evitar excesso de mensagens.",
        ]),
    ]
    for title, bullets in modules:
        h(doc, 2, title)
        for item in bullets:
            bullet(doc, item)


def section_api_offline_security(doc):
    h(doc, 1, "5. API, Offline-First e Seguranca")
    h(doc, 2, "5.1 Endpoints essenciais")
    table(
        doc,
        ["Modulo", "Endpoints principais", "Observacoes"],
        [
            ["Auth", "POST /login, /refresh, /logout, /register", "JWT curto e refresh token rotativo"],
            ["Vehicles", "GET/POST /vehicles, GET/PATCH /vehicles/{id}, /qr-code", "Soft delete e limite por plano"],
            ["Checklists", "/templates, POST /checklists, PATCH /{id}, /complete", "Suporta execucao offline com idempotency key"],
            ["Fuel", "POST /fuel, /stats, /efficiency, /anomalies", "Valida km crescente e anomalias"],
            ["Trips", "POST /trips, /start, /stop, /toll, /complete", "Uma viagem activa por viatura/motorista"],
            ["Maintenance", "/plans, /records, /upcoming, /tires", "Bloqueio de viatura por OS aberta"],
            ["Drivers", "GET/POST /drivers, /score, /incidents", "Dados pessoais protegidos"],
            ["Financial", "/dashboard, /costs, /reports, /projections", "Agregacoes por tenant"],
            ["Alerts", "GET /alerts, /read, /dismiss, /settings", "Prioridade e canais configuraveis"],
        ],
        [1.35, 3.15, 1.9],
        font_size=8.5,
    )
    h(doc, 2, "5.2 Offline-first")
    for item in [
        "Todas as accoes do motorista devem gravar localmente primeiro.",
        "A fila de sincronizacao deve usar idempotency_key para evitar duplicacao.",
        "Fotos devem ser comprimidas localmente antes do upload.",
        "A app deve mostrar claramente: sincronizado, pendente, erro e a tentar novamente.",
        "Conflitos simples podem usar last-write-wins; conflitos financeiros devem ir para revisao do gestor.",
    ]:
        bullet(doc, item)
    h(doc, 2, "5.3 Seguranca")
    for item in [
        "Passwords com bcrypt ou argon2.",
        "Access token de 15 a 30 minutos; refresh token de 7 dias com rotacao.",
        "Rate limit em login, upload e endpoints de sync.",
        "Ficheiros privados em R2 com URLs assinadas.",
        "Auditoria para alteracoes criticas e exportacao de relatorios.",
        "Dados pessoais de motoristas com base legal, consentimento e retencao definida.",
    ]:
        bullet(doc, item)


def section_business_roadmap_ops(doc):
    h(doc, 1, "6. Modelo de Negocio, Roadmap e Operacao")
    h(doc, 2, "6.1 Pricing")
    table(
        doc,
        ["Plano", "Target", "Viaturas", "Preco mensal", "Inclui"],
        [
            ["Solo", "Dono de chapa/moto", "1-3", "400-600 MZN", "Viaturas, checklists, combustivel, viagens simples"],
            ["PME", "Transportadora pequena", "4-15", "250-400 MZN/viatura", "Manutencao, motoristas, alertas WhatsApp"],
            ["Frota", "Empresa media", "16-50", "180-280 MZN/viatura", "Financeiro, relatorios, API"],
            ["Enterprise", "Corporativo/Estado", "51+", "Negociado", "SLA, suporte dedicado, customizacoes"],
        ],
        [1.0, 1.55, 0.8, 1.35, 1.7],
        font_size=8.6,
    )
    h(doc, 2, "6.2 Roadmap recomendado")
    table(
        doc,
        ["Fase", "Duracao", "Entregavel", "Criterio de sucesso"],
        [
            ["MVP", "8 semanas", "Auth, viaturas, checklists, combustivel e viagens", "3 clientes piloto e 50+ checklists reais"],
            ["v1.0", "+6 semanas", "Manutencao, acessorios e motoristas", "Score inicial e historico tecnico por viatura"],
            ["v1.5", "+4 semanas", "Financeiro e relatorios PDF/Excel", "Relatorio mensal aceite por cliente piloto"],
            ["v2.0", "+8 semanas", "Offline completo e WhatsApp avançado", "Zero perda de dados em offline real"],
        ],
        [1.0, 1.0, 2.55, 1.85],
    )
    h(doc, 2, "6.3 Definition of Done")
    for item in [
        "Teste unitario e teste de integracao para fluxos principais.",
        "Validacao de tenant e permissoes em todos os endpoints.",
        "Estados de loading, vazio e erro no frontend.",
        "Logs estruturados e auditoria de operacoes criticas.",
        "Migracao Alembic criada, testada e reversivel quando possivel.",
        "Documentacao OpenAPI coerente e exemplos de payload.",
        "Fluxo testado em ecras pequenos e rede lenta.",
    ]:
        bullet(doc, item)
    h(doc, 2, "6.4 Deploy e observabilidade")
    table(
        doc,
        ["Componente", "Opcao inicial", "Notas"],
        [
            ["Backend", "Render, Railway ou Fly.io", "Docker, healthcheck e logs estruturados"],
            ["DB", "Supabase PostgreSQL", "Backups automaticos, PostGIS e RLS"],
            ["Redis", "Upstash", "Rate limit e filas leves"],
            ["Frontend/PWA", "Vercel ou Cloudflare Pages", "Deploy rapido e CDN"],
            ["Storage", "Cloudflare R2", "Fotos, recibos, documentos e PDFs"],
            ["Erros", "Sentry", "Backend e frontend"],
            ["Produto", "PostHog", "Funis, retencao e uso por modulo"],
        ],
        [1.4, 2.0, 3.0],
    )


def section_risks_next(doc):
    h(doc, 1, "7. Riscos, Mitigacoes e Proximos Passos")
    table(
        doc,
        ["Risco", "Impacto", "Mitigacao"],
        [
            ["Internet instavel", "Perda ou atraso de dados", "Offline-first desde o MVP e fila de sync robusta"],
            ["Baixa literacia digital", "Motorista abandona app", "Fluxos curtos, botoes grandes, linguagem simples e icones"],
            ["Fraude em combustivel", "Perda financeira", "Foto recibo, foto odometro, GPS, limites e anomalias"],
            ["Complexidade excessiva", "MVP atrasa", "Monolito modular e foco em 4 modulos iniciais"],
            ["Custo de WhatsApp", "Margem reduzida", "Alertas configuraveis e envio apenas por excepcao"],
            ["Dados pessoais", "Risco legal", "Consentimento, minimizacao, auditoria e retencao definida"],
            ["Relatorios inconsistentes", "Perda de confianca", "Agregacoes testadas e dados financeiros normalizados"],
        ],
        [1.8, 1.8, 2.8],
    )
    h(doc, 2, "7.1 Proximos passos praticos")
    steps = [
        "Criar repositorio com backend FastAPI e frontend Next.js.",
        "Implementar tenants, users, auth e permissoes.",
        "Criar migrations iniciais: tenants, users, vehicles, files e audit_logs.",
        "Construir modulo de viaturas com upload de fotos/documentos.",
        "Criar templates e execucao de checklist pre-partida.",
        "Prototipar PWA motorista com armazenamento local.",
        "Fechar piloto com 2 a 3 operadores em Maputo.",
    ]
    for idx, step in enumerate(steps, 1):
        para = doc.add_paragraph(style="List Number")
        para.paragraph_format.space_after = Pt(4)
        run = para.add_run(step)
        run.font.name = "Arial"
        run.font.size = Pt(10.5)
    callout(
        doc,
        "Recomendacao final",
        "O MVP deve provar controlo operacional real: menos esquecimentos, menos fraude, mais visibilidade e melhor historico por viatura. A tecnologia deve servir esse resultado, nao competir com ele.",
    )


def build():
    doc = Document()
    style_document(doc)
    cover(doc)

    doc.add_section(WD_SECTION.NEW_PAGE)
    add_header_footer(doc)
    toc(doc)
    section_architecture(doc)
    section_stack(doc)
    section_data(doc)
    section_modules(doc)
    section_api_offline_security(doc)
    section_business_roadmap_ops(doc)
    section_risks_next(doc)
    doc.save(OUT)
    print(OUT)


if __name__ == "__main__":
    build()
