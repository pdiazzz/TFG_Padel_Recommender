from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tfg_padel.reporting import (
    current_summary_from_outputs,
    generate_latex_ready_tables,
    write_memoria_updates,
    write_technical_review,
)


def main() -> None:
    warnings = generate_latex_ready_tables()
    write_memoria_updates()
    write_technical_review(current_summary_from_outputs(), warnings)
    print("Tablas para memoria generadas en outputs/tables/.")
    print("Tablas .tex generadas en outputs/reports/tables_latex/.")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()

