# Átomos de Confusão -- Análise com CodeQL
## Estrutura do projeto

```
codeql-scripts/
├── query/                      # qlpack: uma query .ql por átomo de confusão
│   ├── qlpack.yml
│   ├── codeql-pack.lock.yml    # gerado por "codeql pack install" — versionar
│   ├── condition_operator.ql
│   └── change_of_literal_encoding.ql
├── repos.csv                   # (opcional) lista de repositórios p/ modo em lote
├── run_analysis.py             # script principal de orquestração
├── work/                       # gerado automaticamente — ignorado pelo git
│   ├── repos/                  # clones de repositórios remotos
│   ├── dbs/                    # bancos de dados CodeQL (um por repositório)
│   └── tmp/                    # .bqrs/.csv intermediários de cada query
├── resultado.csv                # gerado: ocorrências por (repositório, átomo)
└── resultado_por_atomo.csv      # gerado (modo em lote, 2+ repos): resumo agregado
```

## Pré-requisitos

- [CodeQL CLI](https://github.com/github/codeql-cli-binaries/releases/latest)
  instalado, atualizado e no PATH (`codeql --version`)
- Python 3.8+
- `git` no PATH (só necessário se algum repositório for informado como URL)

## Como rodar

### Analisar um repositório

```powershell
# Repositório local
python run_analysis.py --repo "C:\caminho\do\repo"

# Repositório remoto (o script clona automaticamente)
python run_analysis.py --repo https://github.com/facebook/react

# Sem argumentos: o script pergunta o caminho/URL interativamente
python run_analysis.py
```

### Analisar vários repositórios de uma vez

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

| Opção         | Padrão            | Descrição                                                  |
|---------------|-------------------|-------------------------------------------------------------|
| `--repo`      | —                 | Caminho local ou URL git de **um** repositório               |
| `--name`      | derivado do caminho | Nome do repositório (usado para nomear o banco de dados)   |
| `--language`  | `javascript`      | Linguagem do repositório                                     |
| `--repos`     | —                 | CSV com `name,source,language` para modo em lote             |
| `--queries`   | `query`           | Pasta do qlpack com os arquivos `.ql`                         |
| `--workdir`   | `work`            | Pasta de trabalho (clones, bancos de dados, temporários)      |
| `--out`       | `resultado.csv`   | Arquivo CSV de saída                                          |
| `--force-db`  | desligado         | Recria o banco de dados mesmo se um já existir                |

`--repo` e `--repos` são mutuamente exclusivos — use um ou outro.

## Como adicionar um novo átomo de confusão

O script não tem os átomos "hardcoded": ele roda **qualquer** arquivo `.ql`
que encontrar na pasta `query/`. Para adicionar um novo átomo (por exemplo,
*Omitted Curly Braces* ou *Comma Operator*, da Tabela 1 do artigo):

1. Crie um novo arquivo `.ql` dentro de `query/`, seguindo o padrão dos
   existentes: `@kind table` no cabeçalho e um `select` final com pelo menos
   `arquivo` e `linha` como colunas.
2. Salve e rode `run_analysis.py` normalmente — o novo átomo aparece
   automaticamente na próxima execução, sem precisar mexer no script.

## Entendendo os resultados

**`resultado.csv`** — uma linha por combinação `(repositório, átomo)`:

| Coluna                  | Significado                                                        |
|--------------------------|--------------------------------------------------------------------|
| `repositorio`            | Nome do repositório analisado                                      |
| `atomo`                  | Nome do átomo (= nome do arquivo `.ql`, sem a extensão)             |
| `ocorrencias`            | Quantas vezes o átomo apareceu no código                           |
| `loc`                    | Linhas de código não-vazias em arquivos `.js/.jsx/.ts/.tsx` (aproximado) |
| `ocorrencias_por_kloc`   | Ocorrências a cada 1000 linhas de código                            |

**`resultado_por_atomo.csv`** (só gerado com 2+ repositórios) — resumo
agregado no mesmo espírito da Tabela 4 do artigo:

| Coluna                        | Significado                                              |
|-------------------------------|-----------------------------------------------------------|
| `pct_projetos_com_atomo`      | % dos repositórios analisados em que o átomo ocorre ≥ 1 vez |
| `media_ocorrencias_por_kloc`  | Média de ocorrências/KLOC entre os repositórios            |

> A contagem de LOC é uma aproximação simples (linhas não-vazias em arquivos
> de código, ignorando `node_modules`). Para números mais próximos aos do
> artigo original, considere substituir por uma chamada à ferramenta
> [`cloc`](https://github.com/AlDanial/cloc).