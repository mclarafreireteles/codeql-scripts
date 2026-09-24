# Átomos de Confusão -- Análise com CodeQL

## Estrutura do projeto

```text
codeql-scripts/
├── query/                      # qlpack: uma query .ql por átomo de confusão
│   ├── qlpack.yml
│   ├── codeql-pack.lock.yml    # gerado por "codeql pack install" — versionar
│   ├── condition_operator.ql
│   └── change_of_literal_encoding.ql
├── repos.csv                   # (opcional) lista de repositórios p/ modo em lote
├── run_analysis.py             # script principal de orquestração
├── resultados/                 # gerado: relatórios de saída
│   └── YYYYMMDD_HHMMSS/        # pasta única por execução (timestamp)
│       ├── resultado.csv       # gerado: resumo de ocorrências
│       ├── resultado_por_atomo.csv # gerado (modo em lote, 2+ repos): resumo agregado
│       └── <nome-do-repo>/     # subpasta para cada repositório analisado
│           └── <atomo>_detalhado.csv # gerado: arquivo, linhas e trecho de código
└── work/                       # gerado automaticamente — ignorado pelo git
    ├── repos/                  # clones de repositórios remotos
    ├── dbs/                    # bancos de dados CodeQL (um por repositório)
    └── tmp/                    # .bqrs/.csv intermediários de cada query
```

## Pré-requisitos

- [CodeQL CLI](https://github.com/github/codeql-cli-binaries/releases/latest)
  instalado, atualizado e no PATH (`codeql --version`)
- Python 3.8+
- `git` no PATH (só necessário se algum repositório for informado como URL)

## Como rodar 

Para rodar esse script você pode escolher por duas maneiras:

### 1. Analisar um repositório

```powershell
# Repositório local
python run_analysis.py --repo "C:\caminho\do\repo"

# Repositório remoto (o script clona automaticamente)
python run_analysis.py --repo https://github.com/facebook/react

# Sem argumentos: o script pergunta o caminho/URL e quais átomos rodar interativamente
python run_analysis.py
```

### 2. Analisar vários repositórios de uma vez

Preencha o `repos.csv`:

```csv
name,source,language
react,https://github.com/facebook/react,javascript
meu-repo,C:\caminho\local\meu-repo,javascript
```

E rode:

```powershell
python run_analysis.py --repos repos.csv
```

### Opções disponíveis

| Opção         | Padrão            | Descrição                                                                 |
|---------------|-------------------|---------------------------------------------------------------------------|
| `--repo`      | —                 | Caminho local ou URL git de **um** repositório                            |
| `--name`      | derivado do caminho | Nome do repositório (usado para nomear o banco de dados)                  |
| `--language`  | `javascript`      | Linguagem do repositório                                                  |
| `--repos`     | —                 | CSV com `name,source,language` para modo em lote                          |
| `--atoms`     | `all`             | Átomos específicos para rodar separados por vírgula (ex: `atom1,atom2`) ou `all` |
| `--queries`   | `query`           | Pasta do qlpack com os arquivos `.ql`                                     |
| `--workdir`   | `work`            | Pasta de trabalho (clones, bancos de dados, temporários)                  |
| `--out`       | `resultado.csv`   | Nome do arquivo CSV de saída geral (salvo dentro da pasta de timestamp)   |
| `--force-db`  | desligado         | Recria o banco de dados mesmo se um já existir                            |

`--repo` e `--repos` são mutuamente exclusivos — use um ou outro.

## Como adicionar um novo átomo de confusão

O script não tem os átomos "hardcoded": ele roda **qualquer** arquivo `.ql`
que encontrar na pasta `query/`. Para adicionar um novo átomo:

1. Crie um novo arquivo `.ql` dentro de `query/`, seguindo o padrão dos
   existentes. **Importante:** para que o script consiga extrair o trecho de código correto, o `select` final deve retornar o nó da AST principal (ex: `select f, "Átomo detectado"`).
2. Salve e rode `run_analysis.py` normalmente — o novo átomo aparece
   automaticamente na próxima execução.

## Entendendo os resultados

Todas as execuções geram uma nova pasta dentro de `resultados/` com a data e hora (ex: `resultados/20231024_153000/`), para não acontecer sobrescritas entre as execuções.

**`resultado.csv`** — uma linha por combinação `(repositório, átomo)`:

| Coluna                  | Significado                                                        |
|-------------------------|--------------------------------------------------------------------|
| `repositorio`           | Nome do repositório analisado                                      |
| `atomo`                 | Nome do átomo (= nome do arquivo `.ql`, sem a extensão)            |
| `ocorrencias`           | Quantas vezes o átomo apareceu no código                           |
| `loc`                   | Linhas de código não-vazias em arquivos `.js/.jsx/.ts/.tsx`        |
| `ocorrencias_por_kloc`  | Ocorrências a cada 1000 linhas de código                           |

**`<nome-do-repo>/<atomo>_detalhado.csv`** — detalhes exatos de onde o átomo foi encontrado:

| Coluna             | Significado                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| `arquivo`          | Caminho relativo do arquivo no repositório                                  |
| `linha_inicio`     | Linha onde o átomo começa                                                   |
| `linha_fim`        | Linha onde o átomo termina                                                  |
| `trecho_codigo`    | O código exato extraído diretamente do arquivo fonte original               |
| `csv_bruto_codeql` | Retorno bruto do CodeQL (para auditoria caso o trecho não seja lido)        |

**`resultado_por_atomo.csv`** (só gerado com 2+ repositórios) — resumo global:

| Coluna                        | Significado                                               |
|-------------------------------|-----------------------------------------------------------|
| `pct_projetos_com_atomo`      | % dos repositórios analisados em que o átomo ocorre ≥ 1 vez |
| `media_ocorrencias_por_kloc`  | Média de ocorrências/KLOC entre os repositórios           |