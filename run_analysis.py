#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_analysis.py -- Executa consultas CodeQL contra repositórios locais ou remotos.
Gera relatórios agregados e detalhados com trechos de código extraídos.
"""

import argparse
import csv
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

CODE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
IGNORE_DIR_NAMES = {"node_modules", "dist", "build", ".git", "vendor", "coverage", ".next"}


def run(cmd, cwd=None, env=None):
    """Executa um comando de subprocesso exibindo a saída no terminal."""
    print(f"\n$ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(cmd, cwd=cwd, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"Comando falhou (codigo {result.returncode}): {' '.join(str(c) for c in cmd)}")
    return result


def derive_name(source: str) -> str:
    cleaned = source.rstrip("/").rstrip("\\")
    last = cleaned.replace("\\", "/").split("/")[-1]
    return last[:-4] if last.endswith(".git") else last


def count_loc(source_dir: Path) -> int:
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
    return db_path.exists() and (db_path / "codeql-database.yml").exists()


def ensure_database(name: str, source_dir: Path, language: str, dbs_dir: Path, force: bool = False) -> Path:
    db_path = dbs_dir / f"{name}-db"

    if force and db_path.exists():
        print(f"[{name}] removendo banco de dados existente em {db_path} (--force-db) ...")
        shutil.rmtree(db_path)

    if db_path.exists() and not is_valid_database(db_path):
        print(f"[{name}] banco de dados incompleto em {db_path}. Removendo e recriando...")
        shutil.rmtree(db_path)

    if db_path.exists():
        print(f"[{name}] banco de dados valido encontrado em {db_path}, pulando criacao.")
        return db_path

    print(f"[{name}] criando banco de dados CodeQL...")
    
    custom_env = os.environ.copy()
    if language == "javascript":
        filters = [
            "exclude:**/*",
            "include:**/*.js",
            "include:**/*.jsx",
            "include:**/*.ts",
            "include:**/*.tsx"
        ]
        custom_env["LGTM_INDEX_FILTERS"] = "\n".join(filters)

    run(["codeql", "database", "create", str(db_path),
         f"--language={language}", f"--source-root={source_dir}"], env=custom_env)
    return db_path


def extract_snippet(source_dir: Path, file_path: str, start_line: int, end_line: int) -> str:
    """Acessa o arquivo original no repositório para extrair as linhas exatas reportadas pela query."""
    if not file_path: return ""
    rel_path = file_path.lstrip("/")
    full_path = source_dir / rel_path
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            start_idx = max(0, start_line - 1)
            end_idx = min(len(lines), end_line)
            return "".join(lines[start_idx:end_idx]).strip()
    except Exception:
        return "[ERRO_AO_LER_ARQUIVO]"


def run_query(db_path: Path, query_path: Path, tmp_dir: Path, source_dir: Path, repo_results_dir: Path) -> int:
    bqrs_path = tmp_dir / f"{query_path.stem}.bqrs"
    csv_path = tmp_dir / f"{query_path.stem}.csv"
    
    run(["codeql", "query", "run", f"--database={db_path}", f"--output={bqrs_path}", str(query_path)])
    run(["codeql", "bqrs", "decode", "--format=csv", f"--output={csv_path}", str(bqrs_path)])
    
    with open(csv_path, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    
    occurrences = max(len(rows) - 1, 0)
    
    if occurrences > 0:
        detailed_rows = []
        for row in rows[1:]:
            file_path = ""
            start_line = end_line = 0
            
            if len(row) >= 5:
                try:
                    start_line = int(row[-4])
                    end_line = int(row[-2])
                    file_path = row[-5]
                except ValueError:
                    pass
            
            trecho = extract_snippet(source_dir, file_path, start_line, end_line)
            detailed_rows.append({
                "arquivo": file_path,
                "linha_inicio": start_line,
                "linha_fim": end_line,
                "trecho_codigo": trecho,
                "csv_bruto_codeql": str(row)
            })
            
        det_csv_path = repo_results_dir / f"{query_path.stem}_detalhado.csv"
        with open(det_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["arquivo", "linha_inicio", "linha_fim", "trecho_codigo", "csv_bruto_codeql"])
            writer.writeheader()
            writer.writerows(detailed_rows)
            
    return occurrences


def print_table(headers, rows):
    if not rows: return
    str_rows = [[str(c) for c in r] for r in rows]
    widths = [max(len(str(h)), *(len(r[i]) for r in str_rows)) for i, h in enumerate(headers)]
    line = "  ".join(str(h).ljust(w) for h, w in zip(headers, widths))
    print(line)
    print("  ".join("-" * w for w in widths))
    for r in str_rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)))


def prompt_for_repo() -> dict:
    print("Nenhum repositorio informado. Vamos configurar um agora.\n")
    source = input("Caminho local ou URL git do repositorio: ").strip()
    while not source:
        source = input("Caminho local ou URL git do repositorio (obrigatorio): ").strip()
    default_name = derive_name(source)
    name = input(f"Nome para identificar esse repositorio [{default_name}]: ").strip() or default_name
    language = input("Linguagem [javascript]: ").strip() or "javascript"
    return {"name": name, "source": source, "language": language}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repo", help="Caminho local ou URL git de UM repositorio")
    parser.add_argument("--name", help="Nome do repositorio informado em --repo")
    parser.add_argument("--language", default="javascript", help="Linguagem do repositorio")
    parser.add_argument("--repos", help="CSV com colunas name,source,language")
    parser.add_argument("--queries", default="query", help="Pasta com os arquivos .ql")
    parser.add_argument("--workdir", default="work", help="Pasta de trabalho para clones/bancos")
    parser.add_argument("--atoms", default="all", help="Átomos específicos separados por vírgula (ex: atom1,atom2) ou 'all'")
    parser.add_argument("--out", default="resultado.csv", help="Nome do CSV de resumo")
    parser.add_argument("--force-db", action="store_true", help="Recria o banco de dados mesmo se ja existir")
    args = parser.parse_args()

    if args.repo and args.repos:
        raise SystemExit("Use --repo OU --repos, nao os dois ao mesmo tempo.")

    is_interactive = not (args.repo or args.repos)
    if is_interactive:
        repos = [prompt_for_repo()]
        atoms_input = input("\nQuais átomos rodar? (separados por vírgula ou 'all' para todos) [all]: ").strip()
        atoms_input = atoms_input or "all"
    else:
        if args.repos:
            with open(args.repos, newline="", encoding="utf-8") as f:
                repos = list(csv.DictReader(f))
        else:
            repos = [{"name": args.name or derive_name(args.repo), "source": args.repo, "language": args.language}]
        atoms_input = args.atoms

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_base_dir = Path("resultados") / timestamp
    results_base_dir.mkdir(parents=True, exist_ok=True)

    workdir = Path(args.workdir)
    repos_dir, dbs_dir, tmp_dir = workdir / "repos", workdir / "dbs", workdir / "tmp"
    for d in (repos_dir, dbs_dir, tmp_dir):
        d.mkdir(parents=True, exist_ok=True)

    query_dir = Path(args.queries)
    query_files = sorted(query_dir.glob("*.ql"))
    
    if atoms_input != "all":
        wanted_atoms = {a.strip() for a in atoms_input.split(",")}
        query_files = [q for q in query_files if q.stem in wanted_atoms]
        
    if not query_files:
        raise SystemExit(f"Nenhuma query correspondente aos átomos informados foi encontrada em {query_dir}")
    print(f"Atomos selecionados ({len(query_files)}): {', '.join(q.stem for q in query_files)}")

    print(f"\nInstalando dependencias do qlpack em {query_dir} ...")
    run(["codeql", "pack", "install"], cwd=str(query_dir))

    rows_out = []
    for repo in repos:
        name = repo["name"]
        source = repo["source"]
        language = repo.get("language") or "javascript"
        
        repo_results_dir = results_base_dir / name
        repo_results_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n=== Repositorio: {name} ===")
        try:
            source_dir = ensure_repo(name, source, repos_dir)
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
                occurrences = run_query(db_path, qf, tmp_dir, source_dir, repo_results_dir)
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

    out_path = results_base_dir / args.out
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["repositorio", "atomo", "ocorrencias", "loc", "ocorrencias_por_kloc"])
        writer.writeheader()
        writer.writerows(rows_out)

    print(f"\n=== Resumo ===")
    print_table(
        ["repositorio", "atomo", "ocorrencias", "loc", "ocorr/KLOC"],
        [[r["repositorio"], r["atomo"], r["ocorrencias"], r["loc"], r["ocorrencias_por_kloc"]] for r in rows_out],
    )
    print(f"\nResultados salvos na pasta: {results_base_dir}")

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


if __name__ == "__main__":
    main()