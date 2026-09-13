#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_analysis.py -- Roda um conjunto de queries CodeQL (uma por atomo de confusao)
contra um repositorio e mostra/salva quantas ocorrencias de cada atomo foram
encontradas. Tambem suporta analisar varios repositorios de uma vez via CSV.

Requisitos:
    - CodeQL CLI no PATH (codeql --version deve funcionar)
    - git no PATH (apenas se o repositorio for uma URL remota)
    - Python 3.8+ (usa somente a biblioteca padrao)

USO SIMPLES (um repositorio por vez):
    python run_analysis.py --repo C:\\caminho\\do\\repo
    python run_analysis.py --repo https://github.com/facebook/react

    Sem nenhum argumento, o script pergunta interativamente:
    python run_analysis.py

USO EM LOTE (varios repositorios de uma vez, via CSV):
    python run_analysis.py --repos repos.csv

    Formato de repos.csv (uma linha por repositorio, com cabecalho):
        name,source,language
        react,https://github.com/facebook/react,javascript
        meu-repo,C:\\caminho\\local\\meu-repo,javascript

Outras opcoes uteis:
    --queries PASTA   Pasta do qlpack com os arquivos .ql (default: query)
    --workdir PASTA   Pasta de trabalho para clones/bancos/temporarios (default: work)
    --out ARQUIVO     CSV de saida (default: resultado.csv)
    --force-db        Recria o banco de dados mesmo se ja existir

Saidas:
    resultado.csv            -- uma linha por (repositorio, atomo): ocorrencias, LOC, ocorr/KLOC
    resultado_por_atomo.csv  -- resumo agregado por atomo (so aparece com 2+ repositorios)
"""

import argparse
import csv
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

CODE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
IGNORE_DIR_NAMES = {"node_modules", "dist", "build", ".git", "vendor", "coverage", ".next"}


def run(cmd, cwd=None):
    """Roda um comando mostrando a saida em tempo real (sem buffer),
    para que o usuario veja o progresso em vez de uma tela parada."""
    print(f"\n$ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"Comando falhou (codigo {result.returncode}): {' '.join(str(c) for c in cmd)}")
    return result


def derive_name(source: str) -> str:
    """Deriva um nome curto a partir de um caminho local ou URL git."""
    cleaned = source.rstrip("/").rstrip("\\")
    last = cleaned.replace("\\", "/").split("/")[-1]
    return last[:-4] if last.endswith(".git") else last


def count_loc(source_dir: Path) -> int:
    """Contagem simples de linhas nao-vazias em arquivos JS/TS.
    Aproximacao rapida; para numeros mais precisos, considere usar a
    ferramenta 'cloc' e substituir esta funcao por uma chamada a ela."""
    import os
    total = 0
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIR_NAMES]
        for fname in files:
            if Path(fname).suffix in CODE_EXTENSIONS:
                fp = Path(root) / fname
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                        total += sum(1 for line in fh if line.strip())
                except OSError:
                    continue
    return total


def ensure_repo(name: str, source: str, repos_dir: Path) -> Path:
    is_remote = source.startswith("http://") or source.startswith("https://") or source.startswith("git@")
    if not is_remote:
        src_path = Path(source)
        if not src_path.exists():
            raise FileNotFoundError(f"Caminho local nao encontrado: {source}")
        return src_path

    dest = repos_dir / name
    if dest.exists():
        print(f"[{name}] repositorio ja clonado em {dest}, pulando clone.")
        return dest
    run(["git", "clone", "--depth", "1", source, str(dest)])
    return dest


def is_valid_database(db_path: Path) -> bool:
    """Um banco de dados CodeQL concluido com sucesso tem esse arquivo de marcacao.
    Se ele nao existir, a criacao provavelmente foi interrompida no meio."""
    return db_path.exists() and (db_path / "codeql-database.yml").exists()


def ensure_database(name: str, source_dir: Path, language: str, dbs_dir: Path, force: bool = False) -> Path:
    db_path = dbs_dir / f"{name}-db"

    if force and db_path.exists():
        print(f"[{name}] --force-db informado: removendo banco de dados existente em {db_path} ...")
        shutil.rmtree(db_path)

    if db_path.exists() and not is_valid_database(db_path):
        print(f"[{name}] banco de dados em {db_path} parece incompleto "
              f"(uma execucao anterior pode ter sido interrompida). Removendo e recriando...")
        shutil.rmtree(db_path)

    if db_path.exists():
        print(f"[{name}] banco de dados ja existe e parece valido em {db_path}, pulando criacao.")
        return db_path

    print(f"[{name}] criando banco de dados CodeQL — em repositorios grandes isso pode levar "
          f"varios minutos. A saida do CodeQL vai aparecer abaixo em tempo real:")
    run(["codeql", "database", "create", str(db_path),
         f"--language={language}", f"--source-root={source_dir}"])
    return db_path


def run_query(db_path: Path, query_path: Path, tmp_dir: Path) -> int:
    """Roda uma query .ql e retorna o numero de ocorrencias (linhas do resultado)."""
    bqrs_path = tmp_dir / f"{query_path.stem}.bqrs"
    csv_path = tmp_dir / f"{query_path.stem}.csv"
    run(["codeql", "query", "run", f"--database={db_path}", f"--output={bqrs_path}", str(query_path)])
    run(["codeql", "bqrs", "decode", "--format=csv", f"--output={csv_path}", str(bqrs_path)])
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return max(len(rows) - 1, 0)  # desconta o cabecalho


def print_table(headers, rows):
    if not rows:
        return
    str_rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(str(h)), *(len(r[i]) for r in str_rows)) for i, h in enumerate(headers)]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("  ".join("-" * w for w in widths))
    for r in str_rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))


def prompt_for_repo() -> dict:
    print("Nenhum repositorio informado via --repo ou --repos. Vamos configurar um agora.\n")
    source = input("Caminho local ou URL git do repositorio: ").strip()
    while not source:
        source = input("Caminho local ou URL git do repositorio (obrigatorio): ").strip()
    default_name = derive_name(source)
    name = input(f"Nome para identificar esse repositorio [{default_name}]: ").strip() or default_name
    language = input("Linguagem [javascript]: ").strip() or "javascript"
    return {"name": name, "source": source, "language": language}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", help="Caminho local ou URL git de UM repositorio (uso simples)")
    parser.add_argument("--name", help="Nome do repositorio informado em --repo (default: derivado do caminho/URL)")
    parser.add_argument("--language", default="javascript", help="Linguagem do repositorio (default: javascript)")
    parser.add_argument("--repos", help="[modo em lote] CSV com colunas name,source,language")
    parser.add_argument("--queries", default="query", help="Pasta do qlpack com os .ql (default: query)")
    parser.add_argument("--workdir", default="work", help="Pasta de trabalho (default: work)")
    parser.add_argument("--out", default="resultado.csv", help="CSV de saida (default: resultado.csv)")
    parser.add_argument("--force-db", action="store_true", help="Recria o banco de dados mesmo se ja existir")
    args = parser.parse_args()

    if args.repo and args.repos:
        raise SystemExit("Use --repo OU --repos, nao os dois ao mesmo tempo.")

    if args.repos:
        with open(args.repos, newline="", encoding="utf-8") as f:
            repos = list(csv.DictReader(f))
    elif args.repo:
        repos = [{"name": args.name or derive_name(args.repo), "source": args.repo, "language": args.language}]
    else:
        repos = [prompt_for_repo()]

    workdir = Path(args.workdir)
    repos_dir, dbs_dir, tmp_dir = workdir / "repos", workdir / "dbs", workdir / "tmp"
    for d in (repos_dir, dbs_dir, tmp_dir):
        d.mkdir(parents=True, exist_ok=True)

    query_dir = Path(args.queries)
    query_files = sorted(query_dir.glob("*.ql"))
    if not query_files:
        raise SystemExit(f"Nenhum arquivo .ql encontrado em {query_dir}")
    print(f"Atomos encontrados ({len(query_files)}): {', '.join(q.stem for q in query_files)}")

    print(f"\nInstalando dependencias do qlpack em {query_dir} ...")
    run(["codeql", "pack", "install"], cwd=str(query_dir))

    rows_out = []
    for repo in repos:
        name = repo["name"]
        source = repo["source"]
        language = repo.get("language") or "javascript"
        print(f"\n=== Repositorio: {name} ===")
        try:
            source_dir = ensure_repo(name, source, repos_dir)
            print(f"[{name}] contando linhas de codigo (pode levar alguns segundos)...")
            loc = count_loc(source_dir)
            print(f"[{name}] LOC (aproximado): {loc}")
            db_path = ensure_database(name, source_dir, language, dbs_dir, force=args.force_db)
        except Exception as e:
            print(f"[{name}] ERRO ao preparar repositorio: {e}", file=sys.stderr)
            continue

        for qf in query_files:
            atom = qf.stem
            occurrences = None
            try:
                occurrences = run_query(db_path, qf, tmp_dir)
            except Exception as e:
                print(f"[{name}/{atom}] ERRO ao rodar query: {e}", file=sys.stderr)

            per_kloc = round(occurrences / (loc / 1000), 3) if occurrences is not None and loc > 0 else None
            rows_out.append({
                "repositorio": name,
                "atomo": atom,
                "ocorrencias": occurrences,
                "loc": loc,
                "ocorrencias_por_kloc": per_kloc,
            })
            status = f"{occurrences} ocorrencias ({per_kloc}/KLOC)" if occurrences is not None else "ERRO"
            print(f"  {atom}: {status}")

    if not rows_out:
        raise SystemExit("\nNenhum resultado gerado (todos os repositorios falharam).")

    out_path = Path(args.out)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["repositorio", "atomo", "ocorrencias", "loc", "ocorrencias_por_kloc"])
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"\n=== Resumo ===")
    print_table(
        ["repositorio", "atomo", "ocorrencias", "loc", "ocorr/KLOC"],
        [[r["repositorio"], r["atomo"], r["ocorrencias"], r["loc"], r["ocorrencias_por_kloc"]] for r in rows_out],
    )
    print(f"\nResultado detalhado salvo em {out_path}")

    total_repos = len({r["repositorio"] for r in rows_out})
    if total_repos > 1:
        by_atom = defaultdict(list)
        for r in rows_out:
            by_atom[r["atomo"]].append(r)

        resumo_path = out_path.with_name(out_path.stem + "_por_atomo.csv")
        with open(resumo_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["atomo", "pct_projetos_com_atomo", "media_ocorrencias_por_kloc"])
            for atom, recs in sorted(by_atom.items()):
                com_atomo = sum(1 for r in recs if r["ocorrencias"] and r["ocorrencias"] > 0)
                pct = round(100 * com_atomo / total_repos, 2) if total_repos else 0
                valid_kloc = [r["ocorrencias_por_kloc"] for r in recs if r["ocorrencias_por_kloc"] is not None]
                media = round(sum(valid_kloc) / len(valid_kloc), 3) if valid_kloc else 0
                writer.writerow([atom, pct, media])
        print(f"Resumo por atomo salvo em {resumo_path}")


if __name__ == "__main__":
    main()