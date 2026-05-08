from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tfg_padel.reporting import current_summary_from_outputs, write_technical_review
from tfg_padel.validation import validate_repository_outputs


def main() -> None:
    summary, _, warnings = validate_repository_outputs()
    write_technical_review(current_summary_from_outputs(), warnings)
    print("Validacion completada.")
    print(f"Filas en data_quality_summary.csv: {len(summary)}")
    print("Outputs: outputs/tables/data_quality_summary.csv, outputs/reports/data_quality_report.md")


if __name__ == "__main__":
    main()

