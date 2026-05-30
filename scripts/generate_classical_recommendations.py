from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tfg_padel.classical_recommender import run_content_based_recommender


def main() -> None:
    try:
        artifacts = run_content_based_recommender(k=3)
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    recommendations = artifacts["recommendations"]
    neighbors = artifacts["neighbors"]
    diagnostics = artifacts["diagnostics"]
    features = artifacts["features"]["feature"].tolist()
    diag = diagnostics.iloc[0].to_dict() if not diagnostics.empty else {}

    print("Línea base basada en contenido")
    print(f"Features usadas: {', '.join(features)}")
    print(f"Orientaciones generadas: {len(recommendations)}")
    print(f"Vecinos generados: {len(neighbors)}")
    print(f"Similitud media: {diag.get('mean_similarity')}")
    print(f"Cobertura: {diag.get('coverage_pct')}%")
    print("Output: outputs/tables/classical_recommendations.csv")
    print("Output: outputs/tables/classical_neighbors.csv")
    print("Output: outputs/tables/classical_recommender_diagnostics.csv")
    print("Output: outputs/reports/classical_recommender_summary.md")
    print(f"Output: {artifacts['classical_report_path'].relative_to(ROOT)}")
    print("Output: outputs/reports/memory_update_classical_recommender.md")
    for warning in artifacts.get("pdf_warnings", []):
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
