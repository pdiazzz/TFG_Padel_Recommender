from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tfg_padel.reporting import current_summary_from_outputs, generate_figures, write_technical_review


def main() -> None:
    warnings = generate_figures()
    write_technical_review(current_summary_from_outputs(), warnings)
    print("Figuras generadas en outputs/figures/.")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()

