# Roubo de rua no Município do Rio de Janeiro (2003–2023)

**Tendência, sazonalidade e ruptura pandêmica nos registros policiais**

[![Artigo](https://img.shields.io/badge/artigo-GitHub%20Pages-2a78d6)](https://raphaelccortes.github.io/roubo-de-rua-rio/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-2a78d6)](https://www.python.org/)
[![Código: MIT](https://img.shields.io/badge/c%C3%B3digo-MIT-0b0b0b)](LICENSE)
[![Dados e texto: CC BY 4.0](https://img.shields.io/badge/dados%20%26%20texto-CC%20BY%204.0-1c5cab)](LICENSE-CC-BY-4.0.md)
[![FAIR](https://img.shields.io/badge/FAIR-compliant-1baf7a)](#princípios-fair)
[![Fonte](https://img.shields.io/badge/dados-DATA.RIO%20%2F%20ISP--RJ-52514e)](https://www.data.rio/documents/5e15538d3a1b47e7a356463a324b21b7/about)

| | |
|---|---|
| **Autor** | Raphael Cortes |
| **Curso** | Bacharelado em Sistemas de Informação — 6º período |
| **Instituição** | Centro Universitário La Salle do Rio de Janeiro (UNILASALLE-RJ) |
| **Disciplina** | Linguagem de Programação (Análise e Visualização de Dados com Python) |
| **Semestre** | 2026.2 |
| **Professor orientador** | Prof. Alexandre Neves Louzada |
| **Artigo publicado** | <https://raphaelccortes.github.io/roubo-de-rua-rio/> |

## Resumo executivo

Este projeto analisa os **937.682 registros de roubo de rua** (roubo a transeunte, roubo de celular e roubo em coletivo) do Município do Rio de Janeiro entre **janeiro de 2003 e outubro de 2023**, publicados pelo DATA.RIO (Tabela 2488) a partir de dados do ISP-RJ. Um pipeline reprodutível em Python lê a planilha original, trata os valores ausentes, valida totais e taxas, ajusta as contagens pelo número de dias de cada mês e decompõe a série por STL robusta.

**Principais achados:**

- **RQ1 — Tendência:** dois ciclos completos de alta e queda. A taxa foi de 394,2 por 100 mil hab. (2003) para 858,5 (2008), caiu para 491,6 (2012), atingiu o pico de **1.030,3 (2017)** e recuou para 561,4 (2022). Para 2023, a estimativa anualizada é de cerca de 460.
- **RQ2 — Sazonalidade:** **fevereiro** é o mês mais crítico (+8,3% acima da tendência) e **dezembro** o mais calmo (−5,9%). A diferença é significativa (Kruskal-Wallis, p ≈ 1,5 × 10⁻⁹) e só aparece quando a contagem é ajustada pelos dias do mês.
- **RQ3 — Pandemia:** queda de **65%** em abril–maio de 2020 em relação a 2019. Ela se sobrepôs a um declínio que já vinha de 2019 e não foi revertida: em 2023, a média diária ficou **53% abaixo** do patamar de 2018–2019.

**Palavras-chave:** segurança pública; roubo de rua; séries temporais; sazonalidade; COVID-19; Rio de Janeiro; dados abertos; FAIR.

## Fonte dos dados

- **Conjunto:** Tabela 2488 — Incidências de roubo de rua, por mês, total, diferenças com relação ao ano anterior, população e taxa por cem mil habitantes segundo o ano, no Município do Rio de Janeiro entre janeiro/2003 – outubro/2023.
- **Publicador:** Instituto Pereira Passos (IPP) / Prefeitura da Cidade do Rio de Janeiro — portal DATA.RIO.
- **Fonte primária:** Instituto de Segurança Pública do Estado do Rio de Janeiro (ISP-RJ) — <http://www.ispdados.rj.gov.br/>.
- **Link perene:** <https://www.data.rio/documents/5e15538d3a1b47e7a356463a324b21b7/about>
- **Arquivo bruto versionado:** [`data/raw/tabela_2488_roubo_de_rua.xls`](data/raw/tabela_2488_roubo_de_rua.xls) (18 KB; SHA-256 `4df1da34…3c50`).
- **Metadados e dicionário de variáveis:** [`data/data_dictionary.md`](data/data_dictionary.md).

## Estrutura do repositório

```
roubo-de-rua-rio/
├── README.md                    # Este arquivo
├── LICENSE                      # MIT (código)
├── LICENSE-CC-BY-4.0.md         # CC BY 4.0 (dados derivados e texto)
├── CITATION.cff                 # Metadados de citação
├── requirements.txt             # Dependências com versões congeladas
├── .gitignore
├── data/
│   ├── raw/                     # Planilha original (.xls), sem alterações
│   ├── processed/               # Dados tratados (Parquet + CSV.gz), métricas e relatório de validação
│   └── data_dictionary.md       # Dicionário de dados (FAIR)
├── notebooks/
│   ├── analise_exploratoria.ipynb   # Exploração, prototipação e validação (executado)
│   └── make_notebook.py             # Gera o notebook a partir de código
├── src/
│   ├── __init__.py
│   ├── etl.py                   # Extração, limpeza, validação e persistência
│   ├── analysis.py              # Métricas das RQs e figuras Plotly
│   ├── build_article.py         # Monta docs/index.html a partir do modelo
│   └── templates/article.html   # Modelo do artigo
└── docs/                        # Artigo publicado via GitHub Pages
    ├── index.html
    └── assets/                  # Figuras interativas (.html) e estáticas (.png)
```

## Como reproduzir

Requisitos: **Python 3.12 ou superior** e Git.

```bash
# 1. Clonar
git clone https://github.com/RAPHAELCCORTES/roubo-de-rua-rio.git
cd roubo-de-rua-rio

# 2. Ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .venv\Scripts\Activate.ps1

# 3. Dependências congeladas
pip install -r requirements.txt

# 4. Pipeline completo
python -m src.etl                # -> data/processed/*.parquet, *.csv.gz, validation_report.json
python -m src.analysis           # -> data/processed/metrics.json, docs/assets/*.html|*.png
python -m src.build_article      # -> docs/index.html

# 5. (Opcional) Reexecutar o notebook
jupyter nbconvert --to notebook --execute --inplace notebooks/analise_exploratoria.ipynb
```

Os PNGs das figuras são exportados com o `kaleido`, que precisa do Google Chrome instalado. Sem ele, o pipeline continua normalmente e gera apenas as versões interativas (`.html`).

Para visualizar o artigo localmente, abra `docs/index.html` no navegador.

## Metodologia (resumo)

1. **ETL** (`src/etl.py`): leitura do `.xls` com `xlrd`; localização dinâmica do cabeçalho; conversão dos marcadores `..`/`...` em `NaN` com registro de cada célula; transformação para formato longo; métricas derivadas (média diária, taxa anualizada, totais jan.–out.); flags de períodos atípicos; validação dos valores publicados; gravação em Parquet e CSV.gz.
2. **Análise** (`src/analysis.py`): taxa anual e fases; STL robusta sobre o log da média diária, com outliers por z-score robusto (|z| > 3,5); índice sazonal pela razão à média móvel 2×12, com teste de Kruskal-Wallis e ε²; comparação mês a mês com 2019 e teste de Mann-Whitney entre os patamares pré e pós-pandemia.
3. **Comunicação** (`src/build_article.py`): artigo HTML5 responsivo com gráficos Plotly interativos, tabela acessível e trechos do código real do pipeline.

## Princípios FAIR

| Princípio | Como é atendido |
|---|---|
| **Findable** | README com resumo, palavras-chave e link perene da fonte; autoria, disciplina, semestre e instituição identificados; `CITATION.cff`; metadados `citation_*` no HTML do artigo |
| **Accessible** | Repositório público; dado bruto versionado (sem login, sem API paga); artigo aberto no GitHub Pages |
| **Interoperable** | Parquet e CSV.gz (UTF-8, ISO 8601); dicionário de dados completo em `data/data_dictionary.md` |
| **Reusable** | Licença MIT (código) e CC BY 4.0 (dados derivados e texto); `requirements.txt` congelado; verificação SHA-256; relatório de validação |

## Licenças

- **Código-fonte:** [MIT](LICENSE).
- **Dados derivados, figuras e texto do artigo:** [Creative Commons Atribuição 4.0 Internacional (CC BY 4.0)](LICENSE-CC-BY-4.0.md).
- **Dados brutos:** pertencem à fonte original (IPP/DATA.RIO e ISP-RJ), redistribuídos com atribuição para fins de reprodutibilidade.

## Como citar

> CORTES, Raphael. **Roubo de rua no Município do Rio de Janeiro (2003–2023)**: tendência, sazonalidade e ruptura pandêmica nos registros policiais. Projeto Final de Disciplina (Sistemas de Informação) — Centro Universitário La Salle do Rio de Janeiro, 2026. Disponível em: https://github.com/RAPHAELCCORTES/roubo-de-rua-rio.
