from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tfg_padel import config
from tfg_padel.io import read_csv_if_exists, write_csv
from tfg_padel.recommender import generate_recommendations
from tfg_padel.reporting import current_summary_from_outputs, write_memoria_updates, write_technical_review


def main() -> None:
    config.ensure_directories()
    player_metrics = read_csv_if_exists(config.PROCESSED_DIR / "player_match_metrics.csv")
    pair_metrics = read_csv_if_exists(config.PROCESSED_DIR / "pair_match_metrics.csv")
    recommendations = generate_recommendations(player_metrics, pair_metrics)
    write_csv(recommendations, config.TABLES_DIR / "recommendations.csv")
    write_csv(recommendations, config.TABLES_DIR / "latex_recommendations.csv")
    write_memoria_updates()
    write_technical_review(current_summary_from_outputs(), [])
    print(f"Recomendaciones generadas: {len(recommendations)}")
    print("Output: outputs/tables/recommendations.csv")


if __name__ == "__main__":
    main()

