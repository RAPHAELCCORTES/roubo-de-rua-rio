"""
Pipeline de ETL — Roubo de rua no Município do Rio de Janeiro (2003–2023).

Fonte: Tabela 2488 do portal DATA.RIO (IPP / Prefeitura do Rio), elaborada a
partir dos registros do Instituto de Segurança Pública (ISP-RJ).

O arquivo bruto é uma planilha Excel 97-2003 (.xls) em formato "largo" e
pensado para impressão: cabeçalho em várias linhas, meses em colunas, notas de
rodapé e marcadores textuais de ausência ("..", "..."). Este módulo:

1. localiza o cabeçalho e as linhas de dados sem depender de posições fixas;
2. converte os marcadores de ausência em NaN, registrando cada ocorrência;
3. transforma a tabela em formato longo (uma linha por mês) e em uma tabela
   anual de conferência;
4. valida os totais, as diferenças e as taxas publicadas, recalculando-os;
5. cria variáveis derivadas (média diária, flags de períodos atípicos);
6. persiste os resultados em Parquet e CSV comprimido (.csv.gz), mais um
   relatório de validação em JSON.

Nenhuma alteração é feita no arquivo bruto: toda transformação é rastreável
neste código e no relatório de validação.

Uso:
    python -m src.etl
"""

from __future__ import annotations

import calendar
import hashlib
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
RAW_FILE = ROOT / "data" / "raw" / "tabela_2488_roubo_de_rua.xls"
PROCESSED_DIR = ROOT / "data" / "processed"

SOURCE_URL = "https://www.data.rio/documents/5e15538d3a1b47e7a356463a324b21b7/about"
RAW_SHA256 = "4df1da3485f3d4d3cd239ffba17672b788881f5e158033e9b48fec8eb04c3a50"

MESES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
         "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
MISSING_MARKERS = {"..", "...", "-", ""}

# Períodos atípicos documentados (ver artigo, seção 2.3)
# - Paralisação da Polícia Civil do RJ: jan–abr/2017 (subnotificação, segundo o ISP)
# - Pandemia de COVID-19: medidas de isolamento a partir de mar/2020
GREVE_PC_2017 = pd.period_range("2017-01", "2017-04", freq="M")
PANDEMIA_INICIO = pd.Period("2020-03", freq="M")
PANDEMIA_FIM = pd.Period("2021-12", freq="M")

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("etl")


# ---------------------------------------------------------------------------
# 1. Extração
# ---------------------------------------------------------------------------
def sha256sum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def read_raw(path: Path = RAW_FILE) -> pd.DataFrame:
    """Lê a primeira planilha do .xls sem cabeçalho (tudo como objeto)."""
    if not path.exists():
        raise FileNotFoundError(
            f"Arquivo bruto não encontrado em {path}. Baixe-o em {SOURCE_URL}"
        )
    digest = sha256sum(path)
    if digest != RAW_SHA256:
        log.warning("SHA-256 do arquivo bruto difere do registrado (%s). "
                    "A fonte pode ter sido atualizada.", digest)
    # engine xlrd: único leitor estável para o formato BIFF (.xls)
    return pd.read_excel(path, sheet_name=0, header=None, dtype=object, engine="xlrd")


def _norm(value) -> str:
    return str(value).strip() if pd.notna(value) else ""


def locate_table(raw: pd.DataFrame) -> tuple[int, dict[str, int]]:
    """Encontra a linha de cabeçalho dos meses e mapeia nome -> índice da coluna.

    Os rótulos originais trazem números de nota colados ("Total2",
    "População3"); por isso a comparação usa prefixos.
    """
    for i, row in raw.iterrows():
        labels = [_norm(v) for v in row.tolist()]
        if "Jan" in labels and "Dez" in labels:
            colmap = {m: labels.index(m) for m in MESES}
            prefixes = {
                "total_oficial": "Total",
                "dif_abs_oficial": "Diferença Absoluta",
                "dif_pct_oficial": "Diferença %",
                "populacao": "População",
                "taxa_100k_oficial": "Taxa por 100 mil",
            }
            for key, prefix in prefixes.items():
                matches = [j for j, lab in enumerate(labels) if lab.startswith(prefix)]
                if len(matches) != 1:
                    raise ValueError(f"Coluna '{prefix}' não encontrada de forma única.")
                colmap[key] = matches[0]
            return i, colmap
    raise ValueError("Cabeçalho com os meses não encontrado na planilha.")


# ---------------------------------------------------------------------------
# 2. Transformação
# ---------------------------------------------------------------------------
def to_number(value, log_missing: list, context: str) -> float:
    """Converte uma célula em float; marcadores de ausência viram NaN (registrados)."""
    if pd.isna(value):
        log_missing.append({"celula": context, "valor_original": None})
        return np.nan
    if isinstance(value, (int, float, np.number)):
        return float(value)
    txt = str(value).strip()
    if txt in MISSING_MARKERS:
        log_missing.append({"celula": context, "valor_original": txt})
        return np.nan
    # números com separador brasileiro, por precaução
    return float(txt.replace(".", "").replace(",", "."))


def extract_year_rows(raw: pd.DataFrame, header_row: int, colmap: dict) -> tuple[pd.DataFrame, list]:
    """Retorna a tabela anual 'larga' (ano x colunas) e o log de valores ausentes."""
    missing: list = []
    records = []
    for i in range(header_row + 1, len(raw)):
        first = _norm(raw.iat[i, 0])
        if not (first.isdigit() and len(first) == 4):
            continue  # linhas vazias, notas e fonte
        ano = int(first)
        rec = {"ano": ano}
        for key, j in colmap.items():
            rec[key] = to_number(raw.iat[i, j], missing, f"{ano}/{key}")
        records.append(rec)
    if not records:
        raise ValueError("Nenhuma linha de dados anual foi encontrada.")
    wide = pd.DataFrame.from_records(records).sort_values("ano").reset_index(drop=True)
    return wide, missing


def to_long(wide: pd.DataFrame) -> pd.DataFrame:
    """Formato longo: uma linha por mês, com variáveis derivadas."""
    long = wide.melt(id_vars="ano", value_vars=MESES, var_name="mes_abrev",
                     value_name="ocorrencias")
    long["mes"] = long["mes_abrev"].map({m: k + 1 for k, m in enumerate(MESES)})
    long = long.dropna(subset=["ocorrencias"])            # nov–dez/2023 ainda não publicados
    long["ocorrencias"] = long["ocorrencias"].round().astype("Int64")

    periodo = pd.PeriodIndex.from_fields(year=long["ano"], month=long["mes"], freq="M")
    long["periodo"] = periodo.astype(str)                  # "2003-01"
    long["data"] = periodo.to_timestamp()                  # 1º dia do mês
    long["dias_no_mes"] = [calendar.monthrange(a, m)[1] for a, m in zip(long["ano"], long["mes"])]
    long["media_diaria"] = long["ocorrencias"].astype(float) / long["dias_no_mes"]

    # População: a tabela não traz a projeção de 2023 (".."). Imputação por
    # LOCF (última observação disponível, 2022), sinalizada em coluna própria.
    pop = wide.set_index("ano")["populacao"]
    long["populacao_imputada"] = long["ano"].map(pop).isna()
    long["populacao_ref"] = long["ano"].map(pop.ffill())
    # taxa mensal anualizada por 100 mil hab. (comparável à taxa anual oficial)
    dias_no_ano = np.where([calendar.isleap(a) for a in long["ano"]], 366, 365)
    long["taxa_anualizada_100k"] = (
        long["media_diaria"] * dias_no_ano / long["populacao_ref"] * 1e5
    )

    long["flag_greve_pc_2017"] = periodo.isin(GREVE_PC_2017)
    long["flag_pandemia"] = (periodo >= PANDEMIA_INICIO) & (periodo <= PANDEMIA_FIM)

    cols = ["data", "periodo", "ano", "mes", "mes_abrev", "ocorrencias", "dias_no_mes",
            "media_diaria", "populacao_ref", "populacao_imputada", "taxa_anualizada_100k",
            "flag_greve_pc_2017", "flag_pandemia"]
    return long[cols].sort_values("data").reset_index(drop=True)


def build_annual(wide: pd.DataFrame, long: pd.DataFrame) -> pd.DataFrame:
    """Tabela anual com valores oficiais e recalculados, lado a lado."""
    g = long.groupby("ano")
    annual = wide[["ano", "total_oficial", "dif_abs_oficial", "dif_pct_oficial",
                   "populacao", "taxa_100k_oficial"]].copy()
    annual["meses_disponiveis"] = annual["ano"].map(g.size()).astype("Int64")
    annual["total_calculado"] = annual["ano"].map(g["ocorrencias"].sum()).astype("Int64")
    jan_out = long[long["mes"] <= 10].groupby("ano")["ocorrencias"].sum()
    annual["total_jan_out"] = annual["ano"].map(jan_out).astype("Int64")

    completo = annual["meses_disponiveis"] == 12
    annual["ano_completo"] = completo
    annual["dif_abs_calculada"] = annual["total_calculado"].astype(float).diff().where(
        completo & completo.shift(1, fill_value=False))
    annual["dif_pct_calculada"] = (
        annual["total_calculado"].astype(float).pct_change() * 100
    ).where(completo & completo.shift(1, fill_value=False))
    annual["taxa_100k_calculada"] = (
        annual["total_calculado"].astype(float) / annual["populacao"] * 1e5
    ).where(completo)
    annual["var_pct_jan_out"] = annual["total_jan_out"].astype(float).pct_change() * 100
    return annual


# ---------------------------------------------------------------------------
# 3. Validação
# ---------------------------------------------------------------------------
def validate(annual: pd.DataFrame, long: pd.DataFrame, missing: list) -> dict:
    """Confere a consistência interna da tabela publicada."""
    report: dict = {"fonte": SOURCE_URL, "sha256_bruto": sha256sum(RAW_FILE)}

    diff_total = (annual["total_calculado"].astype(float) - annual["total_oficial"]).abs()
    report["total_confere"] = bool((diff_total.fillna(0) == 0).all())
    report["anos_total_divergente"] = annual.loc[diff_total > 0, "ano"].tolist()

    comp = annual.dropna(subset=["dif_abs_oficial", "dif_abs_calculada"])
    report["dif_abs_confere"] = bool(np.allclose(comp["dif_abs_oficial"], comp["dif_abs_calculada"]))
    report["dif_pct_max_erro_pp"] = float(
        (comp["dif_pct_oficial"] - comp["dif_pct_calculada"]).abs().max())

    comp = annual.dropna(subset=["taxa_100k_oficial", "taxa_100k_calculada"])
    report["taxa_max_erro"] = float(
        (comp["taxa_100k_oficial"] - comp["taxa_100k_calculada"]).abs().max())

    report["periodo_coberto"] = [long["periodo"].min(), long["periodo"].max()]
    report["n_meses"] = int(len(long))
    report["meses_faltantes_na_serie"] = int(
        len(pd.period_range(long["periodo"].min(), long["periodo"].max(), freq="M")) - len(long))
    report["duplicatas"] = int(long.duplicated(subset=["periodo"]).sum())
    report["ocorrencias_negativas"] = int((long["ocorrencias"] < 0).sum())
    report["valores_ausentes_convertidos"] = missing

    assert report["total_confere"], "Totais anuais não batem com a soma dos meses."
    assert report["meses_faltantes_na_serie"] == 0, "Há buracos na série mensal."
    assert report["duplicatas"] == 0
    assert report["ocorrencias_negativas"] == 0
    return report


# ---------------------------------------------------------------------------
# 4. Carga
# ---------------------------------------------------------------------------
def save(df: pd.DataFrame, name: str) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED_DIR / f"{name}.parquet", index=False)
    df.to_csv(PROCESSED_DIR / f"{name}.csv.gz", index=False, compression="gzip",
              date_format="%Y-%m-%d")
    log.info("Gravado %s (%d linhas) em Parquet e CSV.gz", name, len(df))


def run() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    log.info("Lendo %s", RAW_FILE.name)
    raw = read_raw()
    header_row, colmap = locate_table(raw)
    wide, missing = extract_year_rows(raw, header_row, colmap)
    log.info("%d anos encontrados; %d células ausentes convertidas em NaN",
             len(wide), len(missing))

    long = to_long(wide)
    annual = build_annual(wide, long)
    report = validate(annual, long, missing)

    save(long, "roubo_rua_mensal")
    save(annual, "roubo_rua_anual")
    with open(PROCESSED_DIR / "validation_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log.info("Validação: totais OK=%s | erro máx. taxa=%.4f",
             report["total_confere"], report["taxa_max_erro"])
    return long, annual, report


def load_processed() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Carrega os dados tratados (executa o ETL se ainda não existirem)."""
    m = PROCESSED_DIR / "roubo_rua_mensal.parquet"
    a = PROCESSED_DIR / "roubo_rua_anual.parquet"
    if not (m.exists() and a.exists()):
        run()
    return pd.read_parquet(m), pd.read_parquet(a)


if __name__ == "__main__":
    run()
