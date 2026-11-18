"""
Métricas e visualizações que respondem às perguntas de pesquisa.

RQ1 — Tendência: como a taxa anual de roubo de rua por 100 mil habitantes
      evoluiu de 2003 a 2023 e quais fases podem ser identificadas?
RQ2 — Sazonalidade: existe um padrão mensal recorrente, depois de descontada
      a tendência e o número de dias de cada mês?
RQ3 — Ruptura: qual foi o efeito da pandemia de COVID-19 sobre os registros e
      o patamar voltou ao nível anterior?

Uso:
    python -m src.analysis        # gera data/processed/metrics.json e docs/assets/*
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy import stats
from statsmodels.tsa.seasonal import STL

from src.etl import MESES, PROCESSED_DIR, ROOT, load_processed

ASSETS = ROOT / "docs" / "assets"
log = logging.getLogger("analysis")

# ---------------------------------------------------------------------------
# Identidade visual (paleta validada para daltonismo; texto em tons neutros)
# ---------------------------------------------------------------------------
C = {
    "s1": "#2a78d6",   # série principal (azul)
    "s2": "#eb6834",   # destaque / anomalias (laranja)
    "s3": "#1baf7a",   # aqua
    "s4": "#eda100",   # amarelo
    "ink": "#0b0b0b",
    "ink2": "#52514e",
    "muted": "#8a8984",
    "grid": "#e6e5e0",
    "band": "#f0efec",
    "surface": "#fcfcfb",
}
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
FONT = "Inter, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
Z_LIMIAR = 3.5   # limiar do z-score robusto para outliers


def _layout(fig: go.Figure, title: str, ytitle: str, xtitle: str = "", height: int = 440) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=16, color=C["ink"])),
        font=dict(family=FONT, size=13, color=C["ink2"]),
        paper_bgcolor=C["surface"], plot_bgcolor=C["surface"],
        height=height, margin=dict(l=60, r=24, t=64, b=56),
        hoverlabel=dict(bgcolor="white", bordercolor=C["grid"], font=dict(color=C["ink"], family=FONT)),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, xanchor="left",
                    bgcolor="rgba(0,0,0,0)"),
        separators=",.",   # decimal com vírgula, milhar com ponto
    )
    fig.update_xaxes(title=xtitle, showgrid=False, linecolor=C["grid"], ticks="outside",
                     tickcolor=C["grid"], zeroline=False)
    fig.update_yaxes(title=ytitle, gridcolor=C["grid"], gridwidth=1, zeroline=False,
                     rangemode="tozero")
    return fig


def _br(x: float, nd: int = 1) -> str:
    """Formata número no padrão brasileiro."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------
def decompose(mensal: pd.DataFrame):
    """STL robusta sobre o log da média diária (sazonalidade multiplicativa)."""
    s = mensal.set_index("data")["media_diaria"].asfreq("MS")
    res = STL(np.log(s), period=12, robust=True).fit()
    resid = res.resid
    med = np.median(resid)
    mad = np.median(np.abs(resid - med)) * 1.4826
    z = (resid - med) / mad
    out = pd.DataFrame({
        "media_diaria": s,
        "tendencia": np.exp(res.trend),
        "sazonal": np.exp(res.seasonal),
        "z_robusto": z,
    })
    out["outlier"] = out["z_robusto"].abs() > Z_LIMIAR
    return out


def seasonal_index(mensal: pd.DataFrame) -> pd.DataFrame:
    """Índice sazonal clássico: média diária / média móvel centrada 2x12.

    Exclui os meses atípicos (paralisação de 2017 e pandemia) para que eventos
    pontuais não contaminem o padrão.
    """
    m = mensal.set_index("data")
    s = m["media_diaria"]
    mm = s.rolling(12, center=True).mean().rolling(2).mean().shift(-1)
    idx = (s / mm).rename("indice").to_frame()
    idx["mes"] = idx.index.month
    idx["ano"] = idx.index.year
    mask = ~(m["flag_greve_pc_2017"] | m["flag_pandemia"])
    return idx[mask].dropna()


def compute_metrics(mensal: pd.DataFrame, anual: pd.DataFrame) -> dict:
    met: dict = {}
    comp = anual[anual["ano_completo"]].set_index("ano")
    taxa = comp["taxa_100k_oficial"]

    # --- RQ1 -----------------------------------------------------------------
    pop23 = anual.loc[anual["ano"] == 2022, "populacao"].item()
    m23 = mensal[mensal["ano"] == 2023]
    taxa23_anualizada = m23["ocorrencias"].sum() / m23["dias_no_mes"].sum() * 365 / pop23 * 1e5
    fases = {
        "2003–2008": (2003, 2008), "2008–2012": (2008, 2012),
        "2012–2017": (2012, 2017), "2017–2022": (2017, 2022),
    }
    met["rq1"] = {
        "taxa_2003": taxa[2003], "taxa_2008": taxa[2008], "taxa_2012": taxa[2012],
        "taxa_2017": taxa[2017], "taxa_2018": taxa[2018], "taxa_2022": taxa[2022],
        "taxa_2023_anualizada_jan_out": taxa23_anualizada,
        "ano_pico": int(taxa.idxmax()), "taxa_pico": taxa.max(),
        "total_2003_2022": int(comp["total_oficial"].sum()),
        "total_serie_ate_out_2023": int(mensal["ocorrencias"].sum()),
        "var_fases_pct": {k: (taxa[b] / taxa[a] - 1) * 100 for k, (a, b) in fases.items()},
        "var_2003_2022_pct": (taxa[2022] / taxa[2003] - 1) * 100,
        "jan_out_2022": int(anual.loc[anual["ano"] == 2022, "total_jan_out"].item()),
        "jan_out_2023": int(anual.loc[anual["ano"] == 2023, "total_jan_out"].item()),
        "var_jan_out_2023_pct": float(anual.loc[anual["ano"] == 2023, "var_pct_jan_out"].item()),
        "pico_mensal": mensal.loc[mensal["media_diaria"].idxmax(), ["periodo", "ocorrencias"]].to_dict(),
        "corr_pop_taxa_pearson": float(stats.pearsonr(comp["populacao"], taxa)[0]),
    }
    met["rq1"]["pico_mensal"]["ocorrencias"] = int(met["rq1"]["pico_mensal"]["ocorrencias"])
    # dispersão intra-anual (coeficiente de variação da média diária)
    cv = mensal.groupby("ano")["media_diaria"].agg(lambda x: x.std(ddof=1) / x.mean() * 100)
    met["rq1"]["cv_mediano_pct"] = float(cv.median())
    met["rq1"]["cv_2017_pct"] = float(cv[2017])
    met["rq1"]["cv_2020_pct"] = float(cv[2020])

    # --- Outliers (STL) ------------------------------------------------------
    dec = decompose(mensal)
    outs = dec[dec["outlier"]].copy()
    outs["periodo"] = outs.index.strftime("%Y-%m")
    met["outliers"] = [
        {"periodo": r.periodo, "z": round(float(r.z_robusto), 2),
         "media_diaria": round(float(r.media_diaria), 1)}
        for r in outs.itertuples()
    ]

    # --- RQ2 -----------------------------------------------------------------
    si = seasonal_index(mensal)
    tab = si.groupby("mes")["indice"].agg(["median", "mean", "std", "count"])
    kw = stats.kruskal(*[g["indice"].values for _, g in si.groupby("mes")])
    # tamanho de efeito epsilon² (Tomczak & Tomczak, 2014)
    n = len(si)
    eps2 = (kw.statistic - 12 + 1) / (n - 12)
    # comparação com a contagem bruta (sem ajuste de dias): fevereiro "some"
    bruto = mensal[~(mensal["flag_greve_pc_2017"] | mensal["flag_pandemia"])]
    bruto_rel = bruto.groupby("mes")["ocorrencias"].mean() / bruto["ocorrencias"].mean()
    met["rq2"] = {
        "indice_mediano": {MESES[k - 1]: float(v) for k, v in tab["median"].items()},
        "indice_medio": {MESES[k - 1]: float(v) for k, v in tab["mean"].items()},
        "mes_max": MESES[int(tab["median"].idxmax()) - 1],
        "mes_min": MESES[int(tab["median"].idxmin()) - 1],
        "kruskal_H": float(kw.statistic), "kruskal_p": float(kw.pvalue),
        "epsilon2": float(eps2), "n_obs": int(n),
        "fev_bruto_rel": float(bruto_rel[2]), "fev_por_dia_rel": float(tab["mean"][2]),
        "fev_maior_que_dez_pp": float((tab["median"][2] - tab["median"][12]) * 100),
    }

    # --- RQ3 -----------------------------------------------------------------
    p = mensal.pivot(index="mes", columns="ano", values="media_diaria")
    vs19 = (p.div(p[2019], axis=0) - 1) * 100
    base = mensal[mensal["ano"].isin([2018, 2019])]["media_diaria"].mean()
    def media(anos, meses=range(1, 13)):
        sel = mensal[mensal["ano"].isin(anos) & mensal["mes"].isin(meses)]
        return sel["media_diaria"].mean()
    met["rq3"] = {
        "base_2018_2019_media_diaria": float(base),
        "abr_mai_2020_vs_2019_pct": float(vs19.loc[[4, 5], 2020].mean()),
        "pior_mes_2020": f"2020-{int(vs19[2020].idxmin()):02d}",
        "pior_mes_2020_vs_2019_pct": float(vs19[2020].min()),
        "jan_fev_2020_vs_2019_pct": float((media([2020], [1, 2]) / media([2019], [1, 2]) - 1) * 100),
        "jun_dez_2019_vs_2018_pct": float((media([2019], range(6, 13)) / media([2018], range(6, 13)) - 1) * 100),
        "media_diaria_2018_2019": float(base),
        "media_diaria_2020_mar_dez": float(media([2020], range(3, 13))),
        "media_diaria_2021": float(media([2021])),
        "media_diaria_2022": float(media([2022])),
        "media_diaria_2023_jan_out": float(media([2023], range(1, 11))),
        "var_2022_vs_base_pct": float((media([2022]) / base - 1) * 100),
        "var_2023_vs_base_pct": float((media([2023], range(1, 11)) / base - 1) * 100),
        "var_vs_2019_por_ano_pct": {int(a): float(vs19[a].mean()) for a in [2020, 2021, 2022, 2023]},
    }
    # teste de Mann-Whitney: médias diárias 2018–2019 vs 2022–2023
    pre = mensal[mensal["ano"].isin([2018, 2019])]["media_diaria"]
    pos = mensal[mensal["ano"].isin([2022, 2023])]["media_diaria"]
    mw = stats.mannwhitneyu(pre, pos, alternative="greater")
    met["rq3"]["mannwhitney_U"] = float(mw.statistic)
    met["rq3"]["mannwhitney_p"] = float(mw.pvalue)
    return met


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------
def fig_taxa_anual(anual: pd.DataFrame, met: dict) -> go.Figure:
    comp = anual[anual["ano_completo"]]
    fig = go.Figure()
    # fases (faixas neutras de fundo)
    for x0, x1, nome in [(2003, 2008, "Alta"), (2008, 2012, "Queda"),
                         (2012, 2017, "Alta"), (2017, 2022, "Queda")]:
        if nome == "Queda":
            fig.add_vrect(x0=x0, x1=x1, fillcolor=C["band"], line_width=0, layer="below")
        fig.add_annotation(x=(x0 + x1) / 2, y=1.0, yref="paper", text=f"{nome} {x0}–{x1}",
                           showarrow=False, font=dict(size=11, color=C["ink2"]), yanchor="bottom")
    fig.add_trace(go.Scatter(
        x=comp["ano"], y=comp["taxa_100k_oficial"], mode="lines+markers", name="Taxa anual (oficial)",
        line=dict(color=C["s1"], width=2), marker=dict(size=8, color=C["s1"],
                                                        line=dict(color=C["surface"], width=2)),
        customdata=np.stack([comp["total_oficial"], comp["populacao"]], axis=-1),
        hovertemplate="<b>%{x}</b><br>Taxa: %{y:,.1f} por 100 mil hab."
                      "<br>Ocorrências: %{customdata[0]:,.0f}<br>População: %{customdata[1]:,.0f}<extra></extra>",
    ))
    t23 = met["rq1"]["taxa_2023_anualizada_jan_out"]
    fig.add_trace(go.Scatter(
        x=[2022, 2023], y=[comp["taxa_100k_oficial"].iloc[-1], t23], mode="lines+markers",
        name="2023 (jan–out, anualizada)", line=dict(color=C["s1"], width=2, dash="dot"),
        marker=dict(size=[0, 9], color=C["surface"], line=dict(color=C["s1"], width=2)),
        hovertemplate="<b>2023</b> (jan–out anualizado)<br>Taxa estimada: %{y:,.1f}<extra></extra>",
    ))
    for ano, txt, ay in [(2008, "858,5", -28), (2012, "491,6", 28), (2017, "1.030,3 (pico)", -28),
                         (2003, "394,2", -26), (2022, "561,4", -26)]:
        y = comp.loc[comp["ano"] == ano, "taxa_100k_oficial"].item()
        fig.add_annotation(x=ano, y=y, text=txt, showarrow=False, yshift=-ay * 0.6 if ay > 0 else 16,
                           font=dict(size=12, color=C["ink"]))
    fig.add_annotation(x=2023, y=t23, text=f"{_br(t23)}<br>(est.)", showarrow=False, yshift=-26,
                       font=dict(size=12, color=C["ink"]))
    _layout(fig, "Figura 1 — Taxa anual de roubo de rua por 100 mil habitantes (2003–2023)",
            "Ocorrências por 100 mil hab.")
    fig.update_xaxes(dtick=2, range=[2002.5, 2023.6])
    fig.update_yaxes(range=[0, 1180])
    fig.update_layout(legend=dict(y=-0.2, yanchor="top"), margin=dict(b=80))
    return fig


def fig_serie_mensal(mensal: pd.DataFrame, dec: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_vrect(x0="2017-01-01", x1="2017-04-30", fillcolor=C["band"], line_width=0, layer="below")
    fig.add_vrect(x0="2020-03-01", x1="2021-12-31", fillcolor=C["band"], line_width=0, layer="below")
    fig.add_annotation(x="2017-03-01", y=1.0, yref="paper", text="Paralisação da PCERJ",
                       showarrow=False, yanchor="bottom", font=dict(size=11, color=C["ink2"]))
    fig.add_annotation(x="2021-01-15", y=1.0, yref="paper", text="Pandemia de COVID-19",
                       showarrow=False, yanchor="bottom", font=dict(size=11, color=C["ink2"]))
    fig.add_trace(go.Scatter(
        x=dec.index, y=dec["media_diaria"], mode="lines", name="Média diária no mês",
        line=dict(color=C["s1"], width=1.5),
        hovertemplate="%{x|%m/%Y}<br>Média diária: %{y:,.1f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=dec.index, y=dec["tendencia"], mode="lines", name="Tendência (STL robusta)",
        line=dict(color=C["ink"], width=2),
        hovertemplate="%{x|%m/%Y}<br>Tendência: %{y:,.1f}<extra></extra>",
    ))
    o = dec[dec["outlier"]]
    fig.add_trace(go.Scatter(
        x=o.index, y=o["media_diaria"], mode="markers", name=f"Outlier (|z robusto| > {_br(Z_LIMIAR)})",
        marker=dict(size=9, color=C["s2"], symbol="diamond", line=dict(color=C["surface"], width=2)),
        customdata=o["z_robusto"],
        hovertemplate="%{x|%m/%Y}<br>Média diária: %{y:,.1f}<br>z robusto: %{customdata:,.1f}<extra></extra>",
    ))
    _layout(fig, "Figura 2 — Média diária de roubos de rua por mês, tendência e meses atípicos",
            "Ocorrências por dia", height=460)
    fig.update_xaxes(hoverformat="%m/%Y", dtick="M24", tickformat="%Y")
    fig.update_yaxes(range=[0, 240])
    fig.update_layout(hovermode="x unified", legend=dict(y=-0.16, yanchor="top"),
                      margin=dict(b=80, t=84))
    return fig


def fig_heatmap(mensal: pd.DataFrame) -> go.Figure:
    p = mensal.pivot(index="ano", columns="mes", values="media_diaria").sort_index(ascending=False)
    fig = go.Figure(go.Heatmap(
        z=p.values, x=MESES, y=p.index.astype(str), colorscale=[[i / (len(SEQ_BLUE) - 1), c]
                                                                for i, c in enumerate(SEQ_BLUE)],
        xgap=2, ygap=2, colorbar=dict(title=dict(text="Ocorr./dia", side="right"), thickness=12),
        hovertemplate="%{x}/%{y}<br>Média diária: %{z:,.1f}<extra></extra>",
        hoverongaps=False,
    ))
    _layout(fig, "Figura 3 — Mapa de calor da média diária por ano e mês", "", height=620)
    fig.update_yaxes(rangemode="normal", dtick=1, showgrid=False)
    fig.update_xaxes(side="top", title="")
    fig.update_layout(margin=dict(t=96))
    return fig


def fig_sazonal(mensal: pd.DataFrame) -> go.Figure:
    si = seasonal_index(mensal)
    med = si.groupby("mes")["indice"].median()
    fig = go.Figure()
    fig.add_hline(y=1, line=dict(color=C["muted"], width=1, dash="dash"))
    fig.add_trace(go.Box(
        x=[MESES[m - 1] for m in si["mes"]], y=si["indice"], name="Índice sazonal",
        marker=dict(color=C["s1"], size=5, opacity=0.6), line=dict(color=C["s1"], width=1.5),
        fillcolor="rgba(42,120,214,0.15)", boxpoints="all", jitter=0.35, pointpos=0,
        customdata=si["ano"], showlegend=False,
        hovertemplate="%{x}/%{customdata}<br>Índice: %{y:.3f}<extra></extra>",
    ))
    for m in (2, 12):
        fig.add_annotation(x=MESES[m - 1], y=med[m], text=f"mediana {_br(med[m], 3)}",
                           showarrow=True, arrowhead=0, ax=0, ay=-70 if m == 2 else 52,
                           arrowcolor=C["muted"], font=dict(size=11, color=C["ink"]),
                           bgcolor=C["surface"])
    _layout(fig, "Figura 4 — Índice sazonal mensal (média diária ÷ média móvel 2×12)",
            "Índice (1 = média do ano)")
    fig.update_yaxes(rangemode="normal", range=[0.78, 1.32], tickformat=".2f")
    fig.update_xaxes(categoryorder="array", categoryarray=MESES)
    return fig


def fig_pandemia(mensal: pd.DataFrame) -> go.Figure:
    p = mensal.pivot(index="mes", columns="ano", values="media_diaria")
    vs19 = (p.div(p[2019], axis=0) - 1) * 100
    fig = go.Figure()
    fig.add_hline(y=0, line=dict(color=C["muted"], width=1))
    cores = {2020: C["s1"], 2021: C["s2"], 2022: C["s3"], 2023: C["s4"]}
    simb = {2020: "circle", 2021: "square", 2022: "diamond", 2023: "triangle-up"}
    for ano, cor in cores.items():
        y = vs19[ano].dropna()
        fig.add_trace(go.Scatter(
            x=[MESES[m - 1] for m in y.index], y=y, mode="lines+markers", name=str(ano),
            line=dict(color=cor, width=2), marker=dict(size=8, symbol=simb[ano], color=cor,
                                                       line=dict(color=C["surface"], width=2)),
            hovertemplate=f"%{{x}}/{ano}<br>%{{y:+.1f}}% vs. mesmo mês de 2019<extra></extra>",
        ))
        fig.add_annotation(x=MESES[y.index[-1] - 1], y=y.iloc[-1], text=f"<b>{ano}</b>",
                           xanchor="left", xshift=8, showarrow=False, font=dict(size=12, color=C["ink"]))
    _layout(fig, "Figura 5 — Variação da média diária em relação ao mesmo mês de 2019",
            "Variação vs. 2019 (%)")
    fig.update_yaxes(rangemode="normal", range=[-72, 5], ticksuffix="%")
    fig.update_xaxes(range=[-0.4, 12.0])
    fig.update_layout(hovermode="x unified")
    return fig


def build_figures(mensal: pd.DataFrame, anual: pd.DataFrame, met: dict) -> dict[str, go.Figure]:
    dec = decompose(mensal)
    return {
        "fig1_taxa_anual": fig_taxa_anual(anual, met),
        "fig2_serie_mensal": fig_serie_mensal(mensal, dec),
        "fig3_heatmap": fig_heatmap(mensal),
        "fig4_sazonalidade": fig_sazonal(mensal),
        "fig5_pandemia": fig_pandemia(mensal),
    }


def export_figures(figs: dict[str, go.Figure]) -> None:
    """Exporta cada figura como HTML interativo e, se possível, PNG estático."""
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, fig in figs.items():
        fig.write_html(ASSETS / f"{name}.html", include_plotlyjs="cdn", full_html=True,
                       config={"displaylogo": False, "responsive": True})
        try:   # PNG requer kaleido + Chrome; é opcional para a reprodução
            fig.write_image(ASSETS / f"{name}.png", width=1100, height=fig.layout.height or 440, scale=2)
        except Exception as exc:  # noqa: BLE001
            log.warning("PNG de %s não gerado (%s). O HTML interativo foi salvo.", name, exc)


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    return str(o)


def run() -> tuple[dict, dict]:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    for name in ("kaleido", "choreographer", "logistro"):
        logging.getLogger(name).setLevel(logging.WARNING)
    mensal, anual = load_processed()
    met = compute_metrics(mensal, anual)
    with open(PROCESSED_DIR / "metrics.json", "w", encoding="utf-8") as f:
        json.dump(met, f, ensure_ascii=False, indent=2, default=_json_default)
    log.info("Métricas gravadas em data/processed/metrics.json")
    figs = build_figures(mensal, anual, met)
    export_figures(figs)
    log.info("%d figuras exportadas para docs/assets/", len(figs))
    return met, figs


if __name__ == "__main__":
    run()
