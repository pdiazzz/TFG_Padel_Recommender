from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from . import config
from .cleaning import normalize_column_name
from .io import load_matches_metadata, read_csv_if_exists, read_csv_with_fallback, write_csv


def check_excluded_files() -> list[dict[str, object]]:
    rows = []
    for file_name in config.EXCLUDED_RAW_FILES:
        path = config.RAW_DIR / file_name
        rows.append(
            {
                "file_name": file_name,
                "present_in_raw": path.exists(),
                "policy": "excluded_from_main_outputs",
                "reason": "Version alternativa/duplicada del partido de Madrid; duplicaria observaciones.",
            }
        )
    return rows


def inspect_raw_files(metadata: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    for _, match in metadata.iterrows():
        file_name = str(match["file_name"])
        path = config.RAW_DIR / file_name
        row = {
            "match_id": match["match_id"],
            "file_name": file_name,
            "exists": path.exists(),
            "rows": 0,
            "columns": 0,
            "encoding": "",
            "separator": "",
            "missing_expected_columns": "",
            "warning": "",
        }
        if not path.exists():
            message = f"Fichero no encontrado: {file_name}"
            row["warning"] = message
            warnings.append(message)
            rows.append(row)
            continue

        try:
            raw, read_warnings, info = read_csv_with_fallback(path)
            normalized_columns = {normalize_column_name(column) for column in raw.columns}
            missing = sorted(set(config.EXPECTED_NORMALIZED_COLUMNS) - normalized_columns)
            row.update(
                {
                    "rows": info["rows"],
                    "columns": info["columns"],
                    "encoding": info["encoding"],
                    "separator": info["separator"],
                    "missing_expected_columns": ", ".join(missing),
                    "warning": " | ".join(read_warnings),
                }
            )
            warnings.extend(read_warnings)
            if missing:
                warnings.append(f"{file_name}: columnas esperadas ausentes: {', '.join(missing)}")
        except Exception as exc:
            message = f"Error validando {file_name}: {exc}"
            row["warning"] = message
            warnings.append(message)
        rows.append(row)

    return pd.DataFrame(rows), warnings


def metric_range_warnings(metrics: pd.DataFrame, label: str) -> list[str]:
    warnings: list[str] = []
    if metrics.empty:
        return [f"No hay metricas para validar rangos en {label}."]

    pct_columns = [c for c in ["winner_pct", "error_pct", "presion_ejercida_pct"] if c in metrics.columns]
    for column in pct_columns:
        values = pd.to_numeric(metrics[column], errors="coerce")
        count = int(((values < 0) | (values > 100)).sum())
        if count:
            warnings.append(f"{label}.{column}: {count} valores fuera de [0, 100].")

    if "indice_riesgo" in metrics.columns:
        values = pd.to_numeric(metrics["indice_riesgo"], errors="coerce")
        count = int(((values < 0) | (values > 1)).sum())
        if count:
            warnings.append(f"{label}.indice_riesgo: {count} valores fuera de [0, 1].")

    if "efectividad_ofensiva" in metrics.columns:
        values = pd.to_numeric(metrics["efectividad_ofensiva"], errors="coerce")
        count = int((values < 0).sum())
        if count:
            warnings.append(f"{label}.efectividad_ofensiva: {count} valores negativos.")

    return warnings


def build_quality_summary(
    metadata: pd.DataFrame,
    raw_report: pd.DataFrame,
    matches_clean: pd.DataFrame,
    actions_clean: pd.DataFrame,
    player_metrics: pd.DataFrame,
    pair_metrics: pd.DataFrame,
    extra_warnings: list[str] | None = None,
) -> tuple[pd.DataFrame, str, list[str]]:
    extra_warnings = extra_warnings or []
    warnings: list[str] = list(extra_warnings)

    raw_rows = int(raw_report["rows"].sum()) if "rows" in raw_report.columns else 0
    raw_cols_max = int(raw_report["columns"].max()) if "columns" in raw_report.columns and len(raw_report) else 0
    matches_with_error = (
        int((raw_report["status"] != "ok").sum())
        if "status" in raw_report.columns
        else int((raw_report.get("exists", True) == False).sum())  # noqa: E712
    )
    duplicate_full = int(matches_clean.duplicated().sum()) if not matches_clean.empty else 0
    tagged_shots = int(actions_clean["es_golpe"].sum()) if "es_golpe" in actions_clean.columns else len(actions_clean)
    players = int(actions_clean["jugador"].dropna().nunique()) if "jugador" in actions_clean.columns else 0
    pairs = int(actions_clean["pareja"].dropna().nunique()) if "pareja" in actions_clean.columns else 0

    missing_critical: list[str] = []
    for column in config.CRITICAL_ANALYSIS_COLUMNS:
        if column in matches_clean.columns:
            missing = int(matches_clean[column].isna().sum())
            if missing:
                missing_critical.append(f"{column}:{missing}")
        else:
            missing_critical.append(f"{column}:missing_column")

    range_warnings = metric_range_warnings(player_metrics, "player_match_metrics")
    range_warnings.extend(metric_range_warnings(pair_metrics, "pair_match_metrics"))
    warnings.extend(range_warnings)

    ratio_columns = [
        c
        for c in ["winner_pct", "error_pct", "indice_riesgo", "efectividad_ofensiva", "presion_ejercida_pct"]
        if c in player_metrics.columns
    ]
    controlled_zero_divisions = int(player_metrics[ratio_columns].isna().sum().sum()) if ratio_columns else 0

    excluded_rows = check_excluded_files()
    excluded_present = [row["file_name"] for row in excluded_rows if row["present_in_raw"]]
    excluded_absent = [row["file_name"] for row in excluded_rows if not row["present_in_raw"]]
    if excluded_present:
        warnings.append(
            "Fichero Madrid duplicado detectado y excluido: " + ", ".join(map(str, excluded_present))
        )
    else:
        warnings.append(
            "Fichero Madrid duplicado no encontrado en data/raw; se mantiene politica de exclusion: "
            + ", ".join(map(str, excluded_absent))
        )

    summary_rows = [
        ("partidos_declarados_metadata", len(metadata), "Partidos usados en la experimentacion principal."),
        ("partidos_leidos", int((raw_report["status"] == "ok").sum()) if "status" in raw_report.columns else int(raw_report["exists"].sum()), ""),
        ("partidos_con_error", matches_with_error, ""),
        ("filas_en_crudo", raw_rows, "Suma de filas antes de limpieza/colapsado."),
        ("max_columnas_raw", raw_cols_max, "Maximo de columnas detectado en un CSV."),
        ("filas_limpias", len(matches_clean), "Tras normalizacion y colapsado de eventos."),
        ("duplicados_completos_limpios", duplicate_full, ""),
        ("golpes_etiquetados", tagged_shots, "Acciones analizables con golpe_q y jugador."),
        ("jugadores_detectados", players, ""),
        ("parejas_detectadas", pairs, ""),
        ("ausentes_columnas_criticas", " | ".join(missing_critical), ""),
        ("porcentajes_fuera_de_rango", len(range_warnings), "Detalle en data_quality_report.md."),
        ("divisiones_por_cero_controladas", controlled_zero_divisions, "NaN en ratios donde el denominador es cero o no disponible."),
        ("warnings_formato", len(warnings), "Advertencias acumuladas durante lectura/validacion."),
        ("fichero_madrid_duplicado_excluido", ", ".join(config.EXCLUDED_RAW_FILES), "No usado en metricas principales."),
    ]
    summary = pd.DataFrame(summary_rows, columns=["metric", "value", "notes"])

    missing_by_match = ""
    if "missing_expected_columns" in raw_report.columns:
        missing_lines = []
        for _, row in raw_report.iterrows():
            missing = row.get("missing_expected_columns", "")
            if isinstance(missing, str) and missing.strip():
                missing_lines.append(f"- {row.get('match_id')}: {missing}")
        missing_by_match = "\n".join(missing_lines) if missing_lines else "- No se detectan columnas esperadas ausentes."

    report = f"""# Informe de calidad del dato

## Resumen

- Partidos declarados en metadata: {len(metadata)}
- Partidos leidos correctamente: {summary.loc[summary['metric'] == 'partidos_leidos', 'value'].iloc[0]}
- Partidos con error: {matches_with_error}
- Filas en crudo: {raw_rows}
- Filas limpias: {len(matches_clean)}
- Acciones/golpes analizables: {tagged_shots}
- Jugadores detectados: {players}
- Parejas detectadas: {pairs}
- Duplicados completos tras limpieza: {duplicate_full}

## Valores ausentes en columnas criticas

{chr(10).join(f"- {item}" for item in missing_critical) if missing_critical else "- Sin ausencias criticas detectadas."}

## Columnas esperadas ausentes por partido

{missing_by_match}

## Rangos de metricas

{chr(10).join(f"- {item}" for item in range_warnings) if range_warnings else "- No se detectan porcentajes fuera de rango."}

## Divisiones por cero controladas

Se han identificado {controlled_zero_divisions} valores NaN en ratios derivados. En este proyecto NaN significa que el denominador no existe o es cero; no equivale a rendimiento nulo.

## Advertencias de formato

{chr(10).join(f"- {item}" for item in warnings) if warnings else "- Sin advertencias de formato."}

## Fichero Madrid duplicado/excluido

El fichero `{config.EXCLUDED_RAW_FILES[0]}` queda excluido de los outputs principales por politica metodologica. Estado local: {"detectado y excluido" if excluded_present else "no encontrado en data/raw, pero documentado como excluido"}.
"""

    return summary, report, warnings


def validate_repository_outputs() -> tuple[pd.DataFrame, str, list[str]]:
    config.ensure_directories()
    metadata = load_matches_metadata()
    raw_report, raw_warnings = inspect_raw_files(metadata)

    matches_clean = read_csv_if_exists(config.PROCESSED_DIR / "matches_clean.csv")
    actions_clean = read_csv_if_exists(config.PROCESSED_DIR / "actions_clean.csv")
    player_metrics = read_csv_if_exists(config.PROCESSED_DIR / "player_match_metrics.csv")
    pair_metrics = read_csv_if_exists(config.PROCESSED_DIR / "pair_match_metrics.csv")

    summary, report, warnings = build_quality_summary(
        metadata=metadata,
        raw_report=raw_report.assign(status=raw_report["exists"].map({True: "ok", False: "error"})),
        matches_clean=matches_clean,
        actions_clean=actions_clean,
        player_metrics=player_metrics,
        pair_metrics=pair_metrics,
        extra_warnings=raw_warnings,
    )

    write_csv(summary, config.TABLES_DIR / "data_quality_summary.csv")
    write_csv(raw_report, config.TABLES_DIR / "raw_files_quality.csv")
    (config.REPORTS_DIR / "data_quality_report.md").write_text(report, encoding="utf-8")
    return summary, report, warnings

