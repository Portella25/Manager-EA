from __future__ import annotations

from pathlib import Path

from save_reader import SaveFinder, SaveParser


def print_rows(parser: SaveParser, table: str) -> None:
    print(f"\n[Diagnóstico] Tabela: {table}")
    if table not in parser.available_tables:
        print("  - não encontrada no save")
        return
    rows = parser._execute(f"SELECT * FROM {table} LIMIT 3")
    if not rows:
        print("  - sem linhas retornadas")
        return
    for idx, row in enumerate(rows, start=1):
        print(f"  Linha {idx}: {dict(row)}")


def main() -> None:
    finder = SaveFinder()
    save_path = finder.find_career_save()
    if save_path is None:
        print("[Diagnóstico] Nenhum save de carreira encontrado.")
        return

    parser = SaveParser()
    ok = parser.connect(save_path)
    if not ok:
        print(f"[Diagnóstico] Falha ao abrir save: {save_path}")
        return

    print(f"[Diagnóstico] Save: {save_path}")
    print("[Diagnóstico] Tabelas detectadas:")
    for name in parser.available_tables:
        print(f"  - {name}")

    relevant = [
        "players",
        "career_playercontract",
        "career_injuries",
        "career_transferoffer",
        "career_users",
        "teams",
        "career_calendar",
        "career_playerstats",
    ]
    for table in relevant:
        print_rows(parser, table)

    parser.close()


if __name__ == "__main__":
    main()
