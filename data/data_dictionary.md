# Dicionário de dados

Metadados das variáveis dos conjuntos de dados deste projeto, conforme o princípio **Interoperable** (FAIR).

## Metadados gerais

| Campo | Valor |
|---|---|
| Título | Incidências de roubo de rua no Município do Rio de Janeiro, jan./2003 – out./2023 |
| Fonte primária | Instituto de Segurança Pública do Estado do Rio de Janeiro (ISP-RJ), registros de ocorrência da Polícia Civil |
| Publicador | Instituto Pereira Passos (IPP) — portal DATA.RIO, Tabela 2488 |
| Link perene | <https://www.data.rio/documents/5e15538d3a1b47e7a356463a324b21b7/about> |
| Data de acesso | 18/11/2026 (o IPP registra acesso à fonte ISP em 27/11/2023) |
| Cobertura espacial | Município do Rio de Janeiro (agregado municipal, sem desagregação territorial) |
| Cobertura temporal | Janeiro de 2003 a outubro de 2023 (250 meses) |
| Granularidade | Mensal (série longa) e anual (tabela de conferência) |
| Definição de “roubo de rua” | Soma de roubo a transeunte, roubo de celular e roubo em coletivo (nota 1 da tabela original) |
| Unidade de observação | Registro de ocorrência policial (não equivale necessariamente ao número de crimes ocorridos) |
| Codificação de texto | UTF-8 |
| Separador decimal (CSV) | Ponto (`.`) |
| Formato de datas | ISO 8601 (`AAAA-MM-DD`; período `AAAA-MM`) |
| Licença dos dados derivados | CC BY 4.0 |

## Arquivos

| Arquivo | Descrição | Linhas |
|---|---|---|
| `raw/tabela_2488_roubo_de_rua.xls` | Planilha original baixada do DATA.RIO, sem alterações (SHA-256 `4df1da3485f3d4d3cd239ffba17672b788881f5e158033e9b48fec8eb04c3a50`) | — |
| `processed/roubo_rua_mensal.parquet` / `.csv.gz` | Série longa: uma linha por mês | 250 |
| `processed/roubo_rua_anual.parquet` / `.csv.gz` | Tabela anual com valores oficiais e recalculados | 21 |
| `processed/validation_report.json` | Resultado das checagens de consistência e lista de células ausentes convertidas | — |
| `processed/metrics.json` | Métricas que respondem às perguntas de pesquisa (geradas por `src/analysis.py`) | — |

## `roubo_rua_mensal`

| Variável | Tipo (pandas / Parquet) | Formato / Unidade | Significado | Origem |
|---|---|---|---|---|
| `data` | `datetime64` / timestamp | `AAAA-MM-01` | Primeiro dia do mês de referência | Derivada (ano + mês) |
| `periodo` | `string` | `AAAA-MM` | Mês de referência em texto ISO | Derivada |
| `ano` | `int64` | 2003–2023 | Ano civil | Original (coluna “Ano”) |
| `mes` | `int64` | 1–12 | Número do mês | Derivada (rótulo da coluna) |
| `mes_abrev` | `string` | `Jan`…`Dez` | Abreviação do mês em português | Original (cabeçalho) |
| `ocorrencias` | `Int64` (inteiro anulável) | contagem | Número de registros de roubo de rua no mês | Original (células mensais) |
| `dias_no_mes` | `int64` | 28–31 | Quantidade de dias do mês (considera anos bissextos) | Derivada (`calendar.monthrange`) |
| `media_diaria` | `float64` | ocorrências/dia | `ocorrencias ÷ dias_no_mes`; permite comparar meses de durações diferentes | Derivada |
| `populacao_ref` | `float64` | habitantes | População projetada do ano (ISP). Para 2023, valor de 2022 (LOCF) | Original / imputada |
| `populacao_imputada` | `bool` | `True`/`False` | `True` quando `populacao_ref` foi imputada (meses de 2023) | Derivada |
| `taxa_anualizada_100k` | `float64` | ocorrências por 100 mil hab./ano | `media_diaria × dias_no_ano ÷ populacao_ref × 100.000`; comparável à taxa anual oficial | Derivada |
| `flag_greve_pc_2017` | `bool` | `True`/`False` | Mês afetado pela paralisação da Polícia Civil do RJ (jan.–abr./2017), com subnotificação reconhecida pelo ISP | Derivada (contexto documental) |
| `flag_pandemia` | `bool` | `True`/`False` | Mês do período pandêmico considerado (mar./2020–dez./2021) | Derivada (contexto documental) |

## `roubo_rua_anual`

| Variável | Tipo | Formato / Unidade | Significado | Origem |
|---|---|---|---|---|
| `ano` | `int64` | 2003–2023 | Ano civil | Original |
| `total_oficial` | `float64` | contagem | Total anual publicado (“Total”) | Original |
| `dif_abs_oficial` | `float64` | contagem | Diferença absoluta em relação ao ano anterior. `NaN` em 2003 e 2023 (“..”) | Original |
| `dif_pct_oficial` | `float64` | % | Diferença percentual em relação ao ano anterior. `NaN` em 2003 e 2023 | Original |
| `populacao` | `float64` | habitantes | Projeção populacional do ISP (dezembro ou último mês disponível; julho em 2022). `NaN` em 2023 | Original |
| `taxa_100k_oficial` | `float64` | por 100 mil hab. | Taxa anual publicada. `NaN` em 2023 | Original |
| `meses_disponiveis` | `Int64` | 1–12 | Quantidade de meses com dado no ano | Derivada |
| `total_calculado` | `Int64` | contagem | Soma dos meses (para validar `total_oficial`) | Derivada |
| `total_jan_out` | `Int64` | contagem | Soma de janeiro a outubro (base comparável com 2023) | Derivada |
| `ano_completo` | `bool` | `True`/`False` | `True` se o ano tem os 12 meses | Derivada |
| `dif_abs_calculada` | `float64` | contagem | Diferença absoluta recalculada (apenas entre anos completos) | Derivada |
| `dif_pct_calculada` | `float64` | % | Diferença percentual recalculada | Derivada |
| `taxa_100k_calculada` | `float64` | por 100 mil hab. | Taxa recalculada: `total_calculado ÷ populacao × 100.000` | Derivada |
| `var_pct_jan_out` | `float64` | % | Variação do total jan.–out. em relação ao ano anterior | Derivada |

## Tratamento de valores ausentes

| Marcador na fonte | Significado (legenda da tabela) | Tratamento |
|---|---|---|
| `..` | Não se aplica dado numérico | Convertido em `NaN` e registrado em `validation_report.json` |
| `...` | Dado numérico não disponível | Convertido em `NaN` e registrado (não ocorre nesta versão da tabela) |

Foram encontradas 8 células com marcadores: diferenças de 2003; novembro e dezembro de 2023; diferenças, população e taxa de 2023. Os meses de nov./dez. de 2023 foram **descartados** da série longa (ainda não haviam sido publicados). A população de 2023 foi **imputada** com o valor de 2022 e sinalizada em `populacao_imputada`.

## Validações aplicadas (`src/etl.py → validate`)

* soma dos meses = total anual publicado (todos os anos);
* diferenças absolutas e percentuais recalculadas = publicadas;
* taxa recalculada = taxa publicada (erro máximo 0,0);
* série mensal contínua (sem meses faltantes), sem duplicatas e sem contagens negativas;
* SHA-256 do arquivo bruto conferido a cada execução.
