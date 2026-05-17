from __future__ import annotations

import pandas as pd

from . import config
from .cleaning import collapse_events, normalize_and_clean
from .clustering import run_player_match_clustering
from .features import add_event_flags, get_analyzable_actions
from .io import load_matches_metadata, load_raw_matches, write_csv
from .metrics import (
    compute_pair_global_metrics,
    compute_pair_match_metrics,
    compute_player_global_metrics,
    compute_player_match_metrics,
)
from .recommender import generate_recommendations
from .recommendations_reporting import write_recommendations_summary
from .reporting import (
    build_dataset_summary,
    build_matches_summary,
    write_memoria_updates,
    write_technical_review,
)
from .validation import validate_repository_outputs


def _sort_if_possible(df: pd.DataFrame) -> pd.DataFrame:
    sort_cols = [c for c in ["match_id", "clip_start", "raw_row_number"] if c in df.columns]
    if not sort_cols:
        return df.reset_index(drop=True)
    out = df.copy()
    if "clip_start" in out.columns:
        out["_clip_start_numeric"] = pd.to_numeric(out["clip_start"], errors="coerce")
        sort_cols = ["match_id", "_clip_start_numeric"] + [
            c for c in sort_cols if c not in {"match_id", "clip_start"}
        ]
    out = out.sort_values(sort_cols, kind="stable").drop(columns=["_clip_start_numeric"], errors="ignore")
    return out.reset_index(drop=True)


def run_full_pipeline() -> dict[str, object]:
    config.ensure_directories()
    metadata = load_matches_metadata()
    raw, raw_report, warnings = load_raw_matches(metadata)

    if raw.empty:
        summary = {
            "partidos_procesados": 0,
            "partidos_con_error": len(metadata),
            "filas_totales": 0,
            "acciones_analizables": 0,
            "jugadores_distintos": 0,
            "parejas_distintas": 0,
            "duplicados": 0,
            "outputs_generados": [],
        }
        write_technical_review(summary, warnings)
        return summary

    clean = normalize_and_clean(raw)
    collapsed, duplicates_collapsed, collapse_warnings = collapse_events(clean)
    warnings.extend(collapse_warnings)
    flagged = add_event_flags(collapsed)
    flagged = _sort_if_possible(flagged)
    actions = get_analyzable_actions(flagged)
    actions = _sort_if_possible(actions)

    player_metrics = compute_player_match_metrics(actions)
    pair_metrics = compute_pair_match_metrics(actions)
    player_global = compute_player_global_metrics(player_metrics)
    pair_global = compute_pair_global_metrics(pair_metrics)
    clustering_scores, player_clusters, cluster_profiles, clustering_warnings = run_player_match_clustering(
        player_metrics
    )
    warnings.extend(clustering_warnings)
    recommendations = generate_recommendations(player_metrics, pair_metrics)
    recommendations_summary = write_recommendations_summary(recommendations)

    write_csv(flagged, config.PROCESSED_DIR / "matches_clean.csv")
    write_csv(actions, config.PROCESSED_DIR / "actions_clean.csv")
    write_csv(player_metrics, config.PROCESSED_DIR / "player_match_metrics.csv")
    write_csv(pair_metrics, config.PROCESSED_DIR / "pair_match_metrics.csv")
    write_csv(player_global, config.TABLES_DIR / "player_global_metrics.csv")
    write_csv(pair_global, config.TABLES_DIR / "pair_global_metrics.csv")
    write_csv(clustering_scores, config.TABLES_DIR / "clustering_scores.csv")
    write_csv(player_clusters, config.TABLES_DIR / "player_match_clusters.csv")
    write_csv(cluster_profiles, config.TABLES_DIR / "cluster_profiles.csv")
    write_csv(recommendations, config.TABLES_DIR / "recommendations.csv")
    write_csv(recommendations_summary, config.TABLES_DIR / "recommendations_summary.csv")

    dataset_summary = build_dataset_summary(
        metadata=metadata,
        raw_report=raw_report,
        matches_clean=flagged,
        actions_clean=actions,
        duplicates_collapsed=duplicates_collapsed,
    )
    matches_summary = build_matches_summary(metadata, flagged, actions)
    write_csv(dataset_summary, config.TABLES_DIR / "dataset_summary.csv")
    write_csv(matches_summary, config.TABLES_DIR / "matches_summary.csv")

    quality_summary, _, quality_warnings = validate_repository_outputs()
    warnings.extend(quality_warnings)
    write_memoria_updates()

    output_paths = [
        config.PROCESSED_DIR / "matches_clean.csv",
        config.PROCESSED_DIR / "actions_clean.csv",
        config.PROCESSED_DIR / "player_match_metrics.csv",
        config.PROCESSED_DIR / "pair_match_metrics.csv",
        config.TABLES_DIR / "dataset_summary.csv",
        config.TABLES_DIR / "data_quality_summary.csv",
        config.TABLES_DIR / "player_global_metrics.csv",
        config.TABLES_DIR / "pair_global_metrics.csv",
        config.TABLES_DIR / "clustering_scores.csv",
        config.TABLES_DIR / "player_match_clusters.csv",
        config.TABLES_DIR / "cluster_profiles.csv",
        config.TABLES_DIR / "recommendations.csv",
        config.TABLES_DIR / "recommendations_summary.csv",
        config.REPORTS_DIR / "data_quality_report.md",
        config.REPORTS_DIR / "memoria_updates.md",
    ]
    generated = [str(path.relative_to(config.PROJECT_ROOT)) for path in output_paths if path.exists()]
    summary = {
        "partidos_procesados": int((raw_report["status"] == "ok").sum()),
        "partidos_con_error": int((raw_report["status"] != "ok").sum()),
        "filas_totales": len(flagged),
        "acciones_analizables": len(actions),
        "jugadores_distintos": int(actions["jugador"].dropna().nunique()) if "jugador" in actions.columns else 0,
        "parejas_distintas": int(actions["pareja"].dropna().nunique()) if "pareja" in actions.columns else 0,
        "duplicados": int(duplicates_collapsed),
        "outputs_generados": generated,
        "data_quality_rows": len(quality_summary),
    }
    write_technical_review(summary, warnings)
    return summary


def format_pipeline_summary(summary: dict[str, object]) -> str:
    outputs = summary.get("outputs_generados", [])
    output_text = "\n".join(f"- {item}" for item in outputs) if outputs else "- Sin outputs generados"
    return f"""Resumen final del pipeline

Partidos procesados: {summary.get('partidos_procesados', 0)}
Partidos con error: {summary.get('partidos_con_error', 0)}
Filas totales limpias: {summary.get('filas_totales', 0)}
Golpes/acciones analizables: {summary.get('acciones_analizables', 0)}
Jugadores distintos: {summary.get('jugadores_distintos', 0)}
Parejas distintas: {summary.get('parejas_distintas', 0)}
Duplicados/eventos colapsados: {summary.get('duplicados', 0)}

Outputs generados:
{output_text}
"""
