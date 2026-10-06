"""Exportação do "Stock completo" (Relatórios → Histórico geral) em PDF,
CSV e Excel, com toda a informação dos lotes de sémen e os resumos por
garanhão, proprietário e contentor.

Funções puras sobre o DataFrame de `carregar_stock` (já filtrado pelo
período escolhido na página): sem BD nem Streamlit, para poderem correr
dentro do callable de `st.download_button`.
"""

from __future__ import annotations

import io
import unicodedata
from datetime import datetime

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from modules.mapa_export import texto_celula, texto_pdf

# (coluna em `carregar_stock`, cabeçalho) — tabela "Lotes", com tudo.
COLUNAS_LOTES = [
    ("garanhao_nome", "Garanhão"),
    ("proprietario_nome", "Proprietário"),
    ("data_embriovet", "Data produção"),
    ("origem_externa", "Origem externa"),
    ("palhetas_produzidas", "Palhetas produzidas"),
    ("quantidade_inicial", "Quantidade inicial"),
    ("existencia_atual", "Existência atual"),
    ("qualidade", "Qualidade"),
    ("cor", "Cor"),
    ("concentracao", "Concentração (M/ml)"),
    ("motilidade", "Motilidade (%)"),
    ("certificado", "Certificado"),
    ("dose", "Dose"),
    ("contentor_codigo", "Contentor"),
    ("canister", "Canister"),
    ("andar", "Andar"),
    ("local_armazenagem", "Local (antigo)"),
    ("observacoes", "Observações"),
    ("criado_por", "Criado por"),
    ("data_criacao", "Data de criação"),
]
_INTEIRAS = {"palhetas_produzidas", "quantidade_inicial", "existencia_atual",
             "concentracao", "motilidade", "canister", "andar"}

_CINZA_ESCURO = "#334155"
_CINZA_CLARO = "#f1f5f9"
_LINHA = "#cbd5e1"


def _chave_texto(serie: pd.Series) -> pd.Series:
    """Ordenação alfabética sem acentos nem maiúsculas ("Ópio" junto
    dos "O", não no fim); vazios ficam no fim (NaN mantém-se NaN)."""
    return serie.map(
        lambda v: v if v is None or (isinstance(v, float) and pd.isna(v))
        else unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode().casefold()
    )


def _lotes(stock: pd.DataFrame) -> pd.DataFrame:
    df = stock.copy()
    if "garanhao_nome" not in df.columns and "garanhao" in df.columns:
        df["garanhao_nome"] = df["garanhao"]
    for col, _h in COLUNAS_LOTES:
        if col not in df.columns:
            df[col] = None
    df = df.sort_values(["garanhao_nome", "proprietario_nome"], na_position="last", key=_chave_texto)
    out = df[[c for c, _h in COLUNAS_LOTES]].copy()
    for col in _INTEIRAS:
        out[col] = pd.to_numeric(out[col], errors="coerce").astype("Int64")
    out["data_criacao"] = pd.to_datetime(out["data_criacao"], errors="coerce").dt.strftime("%d/%m/%Y %H:%M")
    out = out.rename(columns=dict(COLUNAS_LOTES))
    return out.reset_index(drop=True)


def _resumo(lotes: pd.DataFrame, por: str, contar: str | None, nome_contar: str | None) -> pd.DataFrame:
    if lotes.empty:
        cols = [por, "Lotes", "Palhetas"] + ([nome_contar] if contar else [])
        return pd.DataFrame(columns=cols)
    base = lotes.copy()
    base[por] = base[por].fillna("—").replace("", "—")
    agg = {"Lotes": (por, "size"), "Palhetas": ("Existência atual", "sum")}
    if contar:
        agg[nome_contar] = (contar, "nunique")
    out = base.groupby(por, dropna=False).agg(**agg).reset_index()
    out["Palhetas"] = out["Palhetas"].fillna(0).astype(int)
    return out.sort_values("Palhetas", ascending=False).reset_index(drop=True)


def tabelas_stock(stock: pd.DataFrame) -> dict:
    """{nome: DataFrame} — "Lotes" com todos os campos e os resumos."""
    lotes = _lotes(stock)
    return {
        "Lotes": lotes,
        "Por garanhão": _resumo(lotes, "Garanhão", "Proprietário", "Proprietários"),
        "Por proprietário": _resumo(lotes, "Proprietário", "Garanhão", "Garanhões"),
        "Por contentor": _resumo(lotes, "Contentor", "Canister", "Canisters"),
    }


# ------------------------------------------------------------------
# CSV
# ------------------------------------------------------------------

def gerar_csv_stock(stock: pd.DataFrame) -> bytes:
    """CSV com a tabela "Lotes" (todos os campos). `utf-8-sig` para o
    Excel abrir os acentos corretamente."""
    return tabelas_stock(stock)["Lotes"].to_csv(index=False).encode("utf-8-sig")


# ------------------------------------------------------------------
# Excel
# ------------------------------------------------------------------

def _valor_excel(v):
    if pd.isna(v):
        return None
    if hasattr(v, "__index__"):  # int / numpy int / Int64
        return int(v)
    return v


def gerar_excel_stock(stock: pd.DataFrame) -> bytes:
    """Excel com uma folha por tabela (Lotes + resumos), prontas a
    imprimir."""
    wb = Workbook()
    wb.remove(wb.active)
    cab_fill = PatternFill("solid", fgColor=_CINZA_CLARO.lstrip("#"))
    borda = Border(bottom=Side(style="thin", color=_LINHA.lstrip("#")))

    for nome, df in tabelas_stock(stock).items():
        ws = wb.create_sheet(nome)
        ws.append(list(df.columns))
        for cel in ws[1]:
            cel.font = Font(bold=True, color=_CINZA_ESCURO.lstrip("#"))
            cel.fill = cab_fill
            cel.border = borda
            cel.alignment = Alignment(vertical="center", wrap_text=True)
        for linha in df.itertuples(index=False):
            ws.append([_valor_excel(v) for v in linha])
        if "Palhetas" in df.columns or "Existência atual" in df.columns:
            col = list(df.columns).index("Palhetas" if "Palhetas" in df.columns else "Existência atual") + 1
            letra, ultima = get_column_letter(col), ws.max_row
            if ultima > 1:
                ws.append([])
                ws.append(["Total"] + [None] * (len(df.columns) - 1))
                ws.cell(row=ws.max_row, column=col, value=f"=SUM({letra}2:{letra}{ultima})")
                for cel in ws[ws.max_row]:
                    cel.font = Font(bold=True)
        for i, cab in enumerate(df.columns, start=1):
            largura = max(len(str(cab)), *(len(texto_celula(v)) for v in df.iloc[:, i - 1].head(200))) if len(df) else len(str(cab))
            ws.column_dimensions[get_column_letter(i)].width = min(45, max(9, largura + 2))
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(len(df.columns))}{max(1, ws.max_row)}"
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_title_rows = "1:1"

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# ------------------------------------------------------------------
# PDF
# ------------------------------------------------------------------

def gerar_pdf_stock(stock: pd.DataFrame, subtitulo: str = "", gerado_em: datetime | None = None) -> bytes:
    """PDF A4 horizontal: resumos na primeira página, depois a tabela de
    lotes. Para caber na largura, alguns campos do lote vão juntos na
    mesma célula (ex.: Contentor / Canister / Andar), mas nenhum fica de
    fora."""
    gerado_em = gerado_em or datetime.now()
    tabelas = tabelas_stock(stock)
    lotes = tabelas["Lotes"]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=1.2 * cm, rightMargin=1.2 * cm, topMargin=1.2 * cm, bottomMargin=1.3 * cm,
        title="Stock completo",
    )
    base = getSampleStyleSheet()
    st_titulo = ParagraphStyle("t", parent=base["Heading1"], fontSize=16, spaceAfter=2,
                               textColor=colors.HexColor(_CINZA_ESCURO))
    st_sub = ParagraphStyle("s", parent=base["Normal"], fontSize=9, textColor=colors.HexColor("#64748b"),
                            spaceAfter=10)
    st_secao = ParagraphStyle("h", parent=base["Heading3"], fontSize=11, spaceBefore=10, spaceAfter=4,
                              textColor=colors.HexColor(_CINZA_ESCURO))
    st_cel = ParagraphStyle("c", parent=base["Normal"], fontSize=7, leading=8.5)
    st_cab = ParagraphStyle("cab", parent=st_cel, fontName="Helvetica-Bold",
                            textColor=colors.HexColor(_CINZA_ESCURO))

    def _tabela(dados, larguras, direita=()):
        tabela = Table(dados, colWidths=[w * cm for w in larguras], repeatRows=1, hAlign="LEFT")
        estilo = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_CINZA_CLARO)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor(_CINZA_ESCURO)),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(_LINHA)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]
        for j in direita:
            estilo.append(("ALIGN", (j, 1), (j, -1), "RIGHT"))
        tabela.setStyle(TableStyle(estilo))
        return tabela

    total = int(pd.to_numeric(lotes["Existência atual"], errors="coerce").fillna(0).sum()) if len(lotes) else 0
    historia = [
        Paragraph("Stock completo de sémen", st_titulo),
        Paragraph(" · ".join(p for p in [
            f"{len(lotes)} lote(s)", f"{total} palhetas", subtitulo,
            f"gerado em {gerado_em:%d/%m/%Y %H:%M}",
        ] if p), st_sub),
    ]

    # Resumos lado a lado não cabem bem com nomes longos — um por baixo do outro.
    for nome in ("Por garanhão", "Por proprietário", "Por contentor"):
        df = tabelas[nome]
        historia.append(Paragraph(nome, st_secao))
        if df.empty:
            historia.append(Paragraph("Sem dados.", st_cel))
            continue
        dados = [list(df.columns)] + [[Paragraph(texto_pdf(v), st_cel) if j == 0 else texto_celula(v)
                                       for j, v in enumerate(linha)] for linha in df.itertuples(index=False)]
        larguras = [9.0] + [2.6] * (len(df.columns) - 1)
        historia.append(_tabela(dados, larguras, direita=range(1, len(df.columns))))

    historia.append(PageBreak())
    historia.append(Paragraph("Lotes", st_titulo))
    historia.append(Spacer(1, 4))
    if lotes.empty:
        historia.append(Paragraph("Sem lotes.", st_cel))
    else:
        # Cabeçalho, largura (cm) e como compor cada célula a partir da linha.
        def _junta(*partes, sep=" / "):
            return sep.join(p for p in (texto_celula(x) for x in partes) if p)

        def _local(r):
            loc = _junta(r["Contentor"],
                         f"C{texto_celula(r['Canister'])}" if texto_celula(r["Canister"]) else "",
                         f"{texto_celula(r['Andar'])}º" if texto_celula(r["Andar"]) else "")
            return loc or texto_celula(r["Local (antigo)"])

        colunas_pdf = [
            ("Garanhão", 3.2, lambda r: texto_celula(r["Garanhão"])),
            ("Proprietário", 3.2, lambda r: texto_celula(r["Proprietário"])),
            ("Data / Origem", 2.2, lambda r: _junta(r["Data produção"], r["Origem externa"])),
            ("Prod. / Inic.", 1.6, lambda r: _junta(r["Palhetas produzidas"], r["Quantidade inicial"])),
            ("Exist.", 1.1, lambda r: texto_celula(r["Existência atual"])),
            ("Qualidade", 1.8, lambda r: texto_celula(r["Qualidade"])),
            ("Cor", 1.3, lambda r: texto_celula(r["Cor"])),
            ("Conc.", 1.3, lambda r: texto_celula(r["Concentração (M/ml)"])),
            ("Mot. %", 1.1, lambda r: texto_celula(r["Motilidade (%)"])),
            ("Cert.", 1.0, lambda r: texto_celula(r["Certificado"])),
            ("Dose", 1.3, lambda r: texto_celula(r["Dose"])),
            ("Localização", 2.4, _local),
            ("Observações", 3.4, lambda r: texto_celula(r["Observações"])),
            ("Criado", 2.4, lambda r: _junta(r["Criado por"], r["Data de criação"], sep=" · ")),
        ]
        numericas = {"Exist.", "Conc.", "Mot. %"}
        st_num = ParagraphStyle("n", parent=st_cel, alignment=2)  # direita
        dados = [[Paragraph(c, st_cab) for c, _w, _f in colunas_pdf]]
        for _, r in lotes.iterrows():
            dados.append([Paragraph(texto_pdf(f(r)), st_num if c in numericas else st_cel)
                          for c, _w, f in colunas_pdf])
        historia.append(_tabela(dados, [w for _c, w, _f in colunas_pdf]))

    def _rodape(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawRightString(doc_.pagesize[0] - doc_.rightMargin, 0.7 * cm, f"Página {doc_.page}")
        canvas.restoreState()

    doc.build(historia, onFirstPage=_rodape, onLaterPages=_rodape)
    return buffer.getvalue()
