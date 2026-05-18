from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tfg_padel.match_dashboards import generate_all_match_dashboards


def main() -> None:
    summary = generate_all_match_dashboards(ROOT)
    ok = summary[summary["status"] == "ok"]
    errors = summary[summary["status"] != "ok"]

    print("Dashboards de partido")
    print(f"Generados correctamente: {len(ok)}")
    print(f"Con error: {len(errors)}")
    print("Output resumen: outputs/tables/match_dashboard_summary.csv")
    for _, row in ok.iterrows():
        print(f"- {row['match_id']}: {row['output_path']}")
    if not errors.empty:
        print("Errores:")
        for _, row in errors.iterrows():
            print(f"- {row['match_id']}: {row['notes']}")


if __name__ == "__main__":
    main()
