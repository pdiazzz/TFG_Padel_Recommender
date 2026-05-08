from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tfg_padel.pipeline import format_pipeline_summary, run_full_pipeline


def main() -> None:
    summary = run_full_pipeline()
    print(format_pipeline_summary(summary))


if __name__ == "__main__":
    main()

