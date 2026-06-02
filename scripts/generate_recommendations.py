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
from tfg_padel.recommendations_reporting import write_recommendations_summary


def main() -> None:
    config.ensure_directories()
    player_metrics = read_csv_if_exists(config.PROCESSED_DIR / "player_match_metrics.csv")
    pair_metrics = read_csv_if_exists(config.PROCESSED_DIR / "pair_match_metrics.csv")
    recommendations = generate_recommendations(player_metrics, pair_metrics)
    warnings: list[str] = []
    try:
        write_csv(recommendations, config.RECOMMENDATIONS_PATH)
    except PermissionError as exc:
        fallback_path = config.TABLES_DIR / "recommendations_new.csv"
        write_csv(recommendations, fallback_path)
        warnings.append(
            f"{exc} Se ha escrito una copia actualizada en {fallback_path}; "
            "cierra el CSV bloqueado y vuelve a ejecutar el script para actualizar la ruta estándar."
        )
    write_csv(recommendations, config.TABLES_DIR / "latex_recommendations.csv")
    summary = write_recommendations_summary(recommendations)
    print(f"Orientaciones tácticas generadas: {len(recommendations)}")
    print(f"Resumen de orientaciones: {len(summary)} filas")
    print("Output: outputs/tables/recommendations.csv")
    print("Output: outputs/tables/recommendations_summary.csv")
    print("Output: outputs/tables/player_recommendation_cards.csv")
    print("Output: outputs/tables/player_global_recommendation_summary.csv")
    print("Output: outputs/tables/match_recommendation_summary.csv")
    for warning in warnings:
        print(f"WARNING: {warning}")


if __name__ == "__main__":
    main()
