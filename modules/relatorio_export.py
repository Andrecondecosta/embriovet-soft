"""Ficheiros (CSV, Excel, PDF) de qualquer relatório da página
Relatórios, feitos a partir das mesmas tabelas que o ecrã mostra.

Os textos já chegam traduzidos; cada tabela é (título, cabeçalhos,
linhas). Os relatórios que já tinham um ficheiro próprio na app antiga
(PDF do garanhão, stock completo) continuam a usá-lo — isto é para os
restantes.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from modules.mapa_export import sem_formula, texto_celula, texto_pdf

# (título, cabeçalhos, linhas[, índices das linhas de total, a negrito])
Tabela = tuple

def _partes(tab) -> tuple[str, list[str], list[list], set[int]]:
    nome, cabecalhos, linhas, *resto = tab
    return nome, cabecalhos, linhas, (resto[0] if resto else set())


_CINZA_ESCURO = "#334155"
_CINZA_CLARO = "#f1f5f9"
_LINHA = "#cbd5e1"


def gerar_csv(titulo: str, kpis: list[tuple[str, int]], tabelas: list[Tabela]) -> bytes:
    """Um CSV por secções (como o do garanhão na app antiga)."""
    saida = io.StringIO()
    w = csv.writer(saida)
    w.writerow([titulo])
    for label, n in kpis:
        w.writerow([label, n])
    for tab in tabelas:
        nome, cabecalhos, linhas, _ = _partes(tab)
        w.writerow([])
        w.writerow([nome])
        w.writerow(cabecalhos)
        w.writerows([[sem_formula(texto_celula(v)) for v in linha] for linha in linhas])
    # BOM para o Excel abrir os acentos bem.
    return ("﻿" + saida.getvalue()).encode("utf-8")


def _nome_folha(nome: str, usados: set) -> str:
    base = "".join(c for c in nome if c not in '[]:*?/\\')[:28] or "Folha"
    final, i = base, 2
    while final in usados:
        final, i = f"{base[:25]} {i}", i + 1
    usados.add(final)
    return final


def gerar_excel(titulo: str, kpis: list[tuple[str, int]], tabelas: list[Tabela]) -> bytes:
    """Uma folha por tabela; os números do topo vão numa folha "Resumo"."""
    wb = Workbook()
    wb.remove(wb.active)
    cab_fill = PatternFill("solid", fgColor=_CINZA_CLARO.lstrip("#"))
    borda = Border(bottom=Side(style="thin", color=_LINHA.lstrip("#")))
    usados: set = set()

    if kpis:
        ws = wb.create_sheet(_nome_folha("Resumo", usados))
        ws.append([titulo])
        ws["A1"].font = Font(bold=True, size=13)
        for label, n in kpis:
            ws.append([label, n])
        ws.column_dimensions["A"].width = 36

    for tab in tabelas:
        nome, cabecalhos, linhas, destaques = _partes(tab)
        ws = wb.create_sheet(_nome_folha(nome, usados))
        ws.append(cabecalhos)
        for cel in ws[1]:
            cel.font = Font(bold=True, color=_CINZA_ESCURO.lstrip("#"))
            cel.fill = cab_fill
            cel.border = borda
            cel.alignment = Alignment(vertical="center", wrap_text=True)
        for i, linha in enumerate(linhas):
            ws.append([v if isinstance(v, (int, float)) else (sem_formula(texto_celula(v)) or None) for v in linha])
            if i in destaques:
                for cel in ws[ws.max_row]:
                    cel.font = Font(bold=True)
                    cel.fill = cab_fill
        for i, cab in enumerate(cabecalhos, start=1):
            largura = max([len(cab)] + [len(texto_celula(l[i - 1])) for l in linhas[:200]])
            ws.column_dimensions[get_column_letter(i)].width = min(45, max(9, largura + 2))
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = f"A1:{get_column_letter(max(1, len(cabecalhos)))}{max(1, ws.max_row)}"
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.print_title_rows = "1:1"

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def gerar_pdf(
    titulo: str,
    subtitulo: str,
    kpis: list[tuple[str, int]],
    tabelas: list[Tabela],
    sem_dados: str = "—",
    gerado_em: datetime | None = None,
) -> bytes:
    """A4 (horizontal quando alguma tabela tem muitas colunas)."""
    gerado_em = gerado_em or datetime.now()
    tabelas = [_partes(tab) for tab in tabelas]
    largo = any(len(cab) > 5 for _, cab, _, _ in tabelas)
    pagina = landscape(A4) if largo else A4
    margem = 1.2 * cm
    util = pagina[0] - 2 * margem

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=pagina, leftMargin=margem, rightMargin=margem, topMargin=margem, bottomMargin=1.3 * cm, title=titulo,
    )
    base = getSampleStyleSheet()
    st_titulo = ParagraphStyle("t", parent=base["Heading1"], fontSize=16, spaceAfter=2, textColor=colors.HexColor(_CINZA_ESCURO))
    st_sub = ParagraphStyle("s", parent=base["Normal"], fontSize=9, textColor=colors.HexColor("#64748b"), spaceAfter=8)
    st_secao = ParagraphStyle("h", parent=base["Heading3"], fontSize=11, spaceBefore=10, spaceAfter=4,
                              textColor=colors.HexColor(_CINZA_ESCURO))
    st_cel = ParagraphStyle("c", parent=base["Normal"], fontSize=7.5, leading=9)
    st_cab = ParagraphStyle("cab", parent=st_cel, fontName="Helvetica-Bold", textColor=colors.HexColor(_CINZA_ESCURO))

    historia = [
        Paragraph(texto_pdf(titulo), st_titulo),
        Paragraph(texto_pdf(" · ".join(p for p in [subtitulo, f"{gerado_em:%d/%m/%Y %H:%M}"] if p)), st_sub),
    ]
    if kpis:
        historia.append(Paragraph(texto_pdf(" · ".join(f"{label}: {n}" for label, n in kpis)), st_sub))

    for nome, cabecalhos, linhas, destaques in tabelas:
        historia.append(Paragraph(texto_pdf(f"{nome} · {len(linhas) - len(destaques)}"), st_secao))
        if not linhas:
            historia.append(Paragraph(texto_pdf(sem_dados), st_cel))
            continue
        numericas = {j for j in range(len(cabecalhos)) if all(isinstance(l[j], (int, float)) or l[j] is None for l in linhas)}
        dados = [[Paragraph(texto_pdf(c), st_cab) for c in cabecalhos]] + [
            [texto_celula(v) if j in numericas else Paragraph(texto_pdf(v), st_cab if i in destaques else st_cel)
             for j, v in enumerate(linha)]
            for i, linha in enumerate(linhas)
        ]
        # Colunas de números estreitas; as de texto repartem o resto.
        n_num = len(numericas)
        estreita = 2.2 * cm
        larga = (util - n_num * estreita) / max(1, len(cabecalhos) - n_num)
        larguras = [estreita if j in numericas else larga for j in range(len(cabecalhos))]
        tabela = Table(dados, colWidths=larguras, repeatRows=1, hAlign="LEFT")
        estilo = [
            ("FONTSIZE", (0, 0), (-1, -1), 7.5),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_CINZA_CLARO)),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor(_LINHA)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ]
        estilo += [("ALIGN", (j, 1), (j, -1), "RIGHT") for j in numericas]
        for i in destaques:  # linhas de total
            estilo += [("FONTNAME", (0, i + 1), (-1, i + 1), "Helvetica-Bold"),
                       ("BACKGROUND", (0, i + 1), (-1, i + 1), colors.HexColor(_CINZA_CLARO))]
        tabela.setStyle(TableStyle(estilo))
        historia.append(tabela)
        historia.append(Spacer(1, 4))

    doc.build(historia)
    return buffer.getvalue()
