"""
Monta o artigo acadêmico estático (docs/index.html).

Lê o modelo em src/templates/article.html e substitui:
  {{FIG:<nome>}}    -> figura Plotly interativa (div) com PNG de reserva
  {{TABELA_ANUAL}}  -> tabela HTML com a série anual (visão acessível dos dados)
  {{CODE:<nome>}}   -> trecho de código-fonte real do pipeline
  {{BUILD_DATE}}    -> data de geração

Uso:
    python -m src.build_article
"""

from __future__ import annotations

import html
import inspect
import logging
import re
import textwrap
from datetime import date

from src import etl
from src.analysis import build_figures, compute_metrics, _br
from src.etl import ROOT, load_processed

TEMPLATE = ROOT / "src" / "templates" / "article.html"
OUTPUT = ROOT / "docs" / "index.html"
log = logging.getLogger("build_article")

PLOTLY_CONFIG = {"displaylogo": False, "responsive": True, "displayModeBar": "hover",
                 "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                 "toImageButtonOptions": {"format": "png", "scale": 2}}


def figure_block(name: str, fig) -> str:
    fig.update_layout(title=None, autosize=True, width=None)
    top = 48 if name == "fig2_serie_mensal" else (72 if name == "fig3_heatmap" else 36)
    fig.update_layout(margin=dict(t=top))
    div = fig.to_html(full_html=False, include_plotlyjs=False, div_id=name,
                      config=PLOTLY_CONFIG, default_width="100%")
    png = f"assets/{name}.png"
    return (f'<div class="plot">{div}</div>'
            f'<noscript><img src="{png}" alt="Versão estática da figura" loading="lazy"></noscript>'
            f'<p class="fig-links"><a href="assets/{name}.html" target="_blank" rel="noopener">abrir em tela cheia</a>'
            f' · <a href="{png}" target="_blank" rel="noopener">PNG em alta resolução</a></p>')


def annual_table(anual) -> str:
    rows = []
    for r in anual.itertuples():
        def cell(v, nd=0, suf=""):
            return "—" if v != v or v is None else _br(float(v), nd) + suf
        nota = "" if r.ano_completo else "<sup>a</sup>"
        rows.append(
            f"<tr><td>{r.ano}{nota}</td><td>{cell(r.total_oficial)}</td>"
            f"<td>{cell(r.dif_pct_oficial, 1, '%')}</td><td>{cell(r.populacao)}</td>"
            f"<td>{cell(r.taxa_100k_oficial, 1)}</td></tr>")
    return "\n".join(rows)


def code_snippet(obj) -> str:
    src = textwrap.dedent(inspect.getsource(obj))
    return f'<pre><code class="language-python">{html.escape(src)}</code></pre>'


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    mensal, anual = load_processed()
    met = compute_metrics(mensal, anual)
    figs = build_figures(mensal, anual, met)

    tpl = TEMPLATE.read_text(encoding="utf-8")
    tpl = re.sub(r"\{\{FIG:(\w+)\}\}", lambda m: figure_block(m.group(1), figs[m.group(1)]), tpl)
    tpl = tpl.replace("{{TABELA_ANUAL}}", annual_table(anual))
    snippets = {"locate_table": etl.locate_table, "to_number": etl.to_number,
                "to_long": etl.to_long, "validate": etl.validate}
    tpl = re.sub(r"\{\{CODE:(\w+)\}\}", lambda m: code_snippet(snippets[m.group(1)]), tpl)
    tpl = tpl.replace("{{BUILD_DATE}}", date.today().strftime("%d/%m/%Y"))

    leftovers = re.findall(r"\{\{[^}]+\}\}", tpl)
    if leftovers:
        raise ValueError(f"Marcadores não substituídos: {leftovers}")
    OUTPUT.write_text(tpl, encoding="utf-8")
    log.info("Artigo gerado em %s (%.0f KB)", OUTPUT.relative_to(ROOT), OUTPUT.stat().st_size / 1024)


if __name__ == "__main__":
    run()
