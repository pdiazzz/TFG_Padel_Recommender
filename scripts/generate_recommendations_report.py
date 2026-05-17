from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tfg_padel.recommendations_reporting import generate_recommendations_report


def main() -> None:
    try:
        artifacts = generate_recommendations_report()
    except FileNotFoundError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    summary = artifacts["summary"]
    recommendations = artifacts["recommendations"]
    cards = artifacts["cards"]
    global_summary = artifacts["global_summary"]
    total = int(summary.loc[summary["category"] == "all", "count"].iloc[0])
    insufficient = int(summary.loc[summary["category"] == "insufficient_evidence", "count"].iloc[0])
    pair_recommendations = int((recommendations["scope"] == "pair").sum())
    print(f"Recomendaciones en CSV: {total}")
    print(f"Recomendaciones reales: {total - insufficient}")
    print(f"Sin evidencia suficiente: {insufficient}")
    print(f"Fichas jugador-partido: {len(cards)}")
    print(f"Jugadores con ficha: {cards['player'].nunique() if not cards.empty else 0}")
    print(f"Recomendaciones de pareja: {pair_recommendations}")
    print("Output: outputs/tables/recommendations_summary.csv")
    print("Output: outputs/tables/player_recommendation_cards.csv")
    print("Output: outputs/tables/player_global_recommendation_summary.csv")
    print("Output: outputs/tables/match_recommendation_summary.csv")
    print("Output: outputs/reports/tables_latex/recommendations_summary.tex")
    print("Output: outputs/reports/tables_latex/player_recommendation_examples.tex")
    print("Output: outputs/reports/tables_latex/global_player_summary.tex")
    print(f"Output: {artifacts['recommendations_report'].relative_to(ROOT)}")
    print(f"Output: {artifacts['cards_report'].relative_to(ROOT)}")
    for warning in artifacts.get("pdf_warnings", []):
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
