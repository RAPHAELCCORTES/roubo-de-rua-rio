"""Gera (e opcionalmente executa) notebooks/analise_exploratoria.ipynb.

O notebook é mantido como código para que diffs sejam legíveis no Git.
Uso:
    python notebooks/make_notebook.py
    jupyter nbconvert --to notebook --execute --inplace notebooks/analise_exploratoria.ipynb
"""
from pathlib import Path

import nbformat as nbf

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell

cells = [
    md("""# Análise exploratória — Roubo de rua no Município do Rio de Janeiro (2003–2023)

**Autor:** Raphael Cortes · **Curso:** Sistemas de Informação (6º período) — UNILASALLE-RJ
**Disciplina:** Linguagem de Programação (Análise e Visualização de Dados com Python) · **Semestre:** 2026.2
**Professor orientador:** Prof. Alexandre Neves Louzada

**Fonte:** [DATA.RIO — Tabela 2488](https://www.data.rio/documents/5e15538d3a1b47e7a356463a324b21b7/about) (IPP, a partir de dados do ISP-RJ)

Este notebook documenta a exploração preliminar, a prototipação e a validação das métricas.
A lógica definitiva foi consolidada nos módulos reutilizáveis de `src/` (`etl.py`, `analysis.py`);
aqui eles são importados e inspecionados passo a passo."""),
    code("""import sys
from pathlib import Path

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import plotly.io as pio
from scipy import stats

from src import etl, analysis

# Interativo no Jupyter + PNG embutido (para visualização no GitHub), se o kaleido estiver disponível
try:
    import plotly.graph_objects as go
    pio.to_image(go.Figure(), format="png")
    pio.renderers.default = "notebook_connected+png"
except Exception:
    pio.renderers.default = "notebook_connected"
pd.set_option("display.max_columns", 30)
pd.set_option("display.width", 160)"""),
    md("""## 1. Inspeção do arquivo bruto

A planilha é um `.xls` (Excel 97–2003) desenhado para impressão: título, cabeçalho em duas linhas,
meses em colunas, notas de rodapé e marcadores textuais de ausência (`..` e `...`)."""),
    code("""raw = etl.read_raw()
print("Dimensões da planilha bruta:", raw.shape)
raw.head(12)"""),
    code("""# Rodapé com fonte e notas metodológicas
raw.iloc[31:, 0].dropna().tolist()"""),
    md("""## 2. ETL

`etl.run()` localiza o cabeçalho dinamicamente, converte marcadores de ausência em `NaN`
(registrando cada célula), reorganiza para formato longo, cria métricas derivadas,
valida os totais publicados e persiste em Parquet e CSV.gz."""),
    code("""mensal, anual, report = etl.run()
print({k: v for k, v in report.items() if k != "valores_ausentes_convertidos"})"""),
    code("""pd.DataFrame(report["valores_ausentes_convertidos"])"""),
    code("""mensal.info()
mensal.head()"""),
    md("""### 2.1 Conferência dos valores oficiais

Os totais, as diferenças e as taxas recalculados batem exatamente com os publicados."""),
    code("""anual[["ano", "total_oficial", "total_calculado", "dif_pct_oficial", "dif_pct_calculada",
       "taxa_100k_oficial", "taxa_100k_calculada"]].round(2)"""),
    md("""## 3. Estatística descritiva"""),
    code("""mensal[["ocorrencias", "media_diaria", "taxa_anualizada_100k"]].describe().round(2)"""),
    code("""# Dispersão intra-anual: coeficiente de variação (%) da média diária
cv = mensal.groupby("ano")["media_diaria"].agg(lambda x: x.std(ddof=1) / x.mean() * 100).round(1)
cv.to_frame("CV (%)").T"""),
    code("""# A população explica a variação da taxa? (correlação fraca)
comp = anual[anual["ano_completo"]]
r, p = stats.pearsonr(comp["populacao"], comp["taxa_100k_oficial"])
print(f"Pearson r = {r:.3f} (p = {p:.3f}); crescimento populacional 2003→2022: "
      f"{(comp['populacao'].iloc[-1] / comp['populacao'].iloc[0] - 1) * 100:.1f}%")"""),
    md("""## 4. RQ1 — Tendência"""),
    code("""met = analysis.compute_metrics(mensal, anual)
figs = analysis.build_figures(mensal, anual, met)
{k: (round(v, 2) if isinstance(v, float) else v) for k, v in met["rq1"].items()}"""),
    code("""figs["fig1_taxa_anual"].show()"""),
    md("""### 4.1 Decomposição STL e detecção de meses atípicos

STL robusta sobre `log(média diária)`; resíduos padronizados por z-score robusto (mediana/MAD).
Limiar |z| > 3,5 (Iglewicz & Hoaglin, 1993)."""),
    code("""dec = analysis.decompose(mensal)
dec[dec["outlier"]].round(2)"""),
    code("""figs["fig2_serie_mensal"].show()"""),
    md("""## 5. RQ2 — Sazonalidade"""),
    code("""# Contagem bruta vs. média diária: fevereiro muda de posição
tipico = mensal[~(mensal["flag_greve_pc_2017"] | mensal["flag_pandemia"])]
comparacao = pd.DataFrame({
    "contagem_bruta_rel": tipico.groupby("mes")["ocorrencias"].mean() / tipico["ocorrencias"].mean(),
    "indice_sazonal_mediano": analysis.seasonal_index(mensal).groupby("mes")["indice"].median(),
}).round(3)
comparacao.index = etl.MESES
comparacao"""),
    code("""print(f"Kruskal-Wallis H = {met['rq2']['kruskal_H']:.2f}; p = {met['rq2']['kruskal_p']:.2e}; "
      f"epsilon² = {met['rq2']['epsilon2']:.3f}; n = {met['rq2']['n_obs']}")"""),
    code("""figs["fig3_heatmap"].show()
figs["fig4_sazonalidade"].show()"""),
    md("""## 6. RQ3 — Pandemia de COVID-19"""),
    code("""p = mensal.pivot(index="mes", columns="ano", values="media_diaria")
vs19 = ((p.div(p[2019], axis=0) - 1) * 100)[[2020, 2021, 2022, 2023]].round(1)
vs19.index = etl.MESES
vs19"""),
    code("""{k: (round(v, 2) if isinstance(v, float) else v) for k, v in met["rq3"].items()}"""),
    code("""figs["fig5_pandemia"].show()"""),
    md("""## 7. Síntese

* **RQ1:** dois ciclos completos (alta 2003–2008, queda 2008–2012, alta 2012–2017, queda 2017–2022); pico em 2017 provavelmente subestimado pela paralisação da Polícia Civil.
* **RQ2:** fevereiro é o mês mais crítico por dia (índice mediano ≈ 1,08) e dezembro o mais calmo (≈ 0,94); diferença significativa (Kruskal-Wallis).
* **RQ3:** queda de ~65% em abr.–mai./2020 vs. 2019, sobreposta a um declínio iniciado em 2019; patamar de 2022–2023 cerca de metade do de 2018–2019.

A discussão completa está no artigo em `docs/index.html`."""),
]

nb = nbf.v4.new_notebook(cells=cells, metadata={
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
})
out = Path(__file__).with_name("analise_exploratoria.ipynb")
nbf.write(nb, out)
print(f"Notebook gravado em {out}")
