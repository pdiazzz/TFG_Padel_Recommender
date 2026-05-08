from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def safe_divide(numerator: pd.Series, denominator: pd.Series, multiplier: float = 1.0) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    result = numerator / denominator.replace(0, np.nan) * multiplier
    return result.replace([np.inf, -np.inf], np.nan)


def _round_numeric(df: pd.DataFrame, decimals: int = 4) -> pd.DataFrame:
    out = df.copy()
    numeric_cols = out.select_dtypes(include=["number"]).columns
    out[numeric_cols] = out[numeric_cols].round(decimals)
    return out


def compute_player_match_metrics(actions: pd.DataFrame) -> pd.DataFrame:
    if actions.empty:
        return pd.DataFrame(columns=config.PLAYER_METRIC_COLUMNS)

    group_cols = ["match_id", "tournament", "round", "jugador", "pareja"]
    grouped = (
        actions.groupby(group_cols, dropna=False)
        .agg(
            total_golpes=("es_golpe", "sum"),
            winners=("es_winner", "sum"),
            errores_totales=("es_error", "sum"),
            errores_no_forzados=("es_error_no_forzado", "sum"),
            errores_forzados_provocados=("es_fuerza_error", "sum"),
            servicios=("es_servicio", "sum"),
        )
        .reset_index()
    )

    grouped["winner_pct"] = safe_divide(grouped["winners"], grouped["total_golpes"], 100)
    grouped["error_pct"] = safe_divide(grouped["errores_totales"], grouped["total_golpes"], 100)
    grouped["indice_riesgo"] = safe_divide(grouped["errores_no_forzados"], grouped["errores_totales"])
    grouped["efectividad_ofensiva"] = safe_divide(grouped["winners"], grouped["errores_no_forzados"])
    grouped["presion_ejercida_pct"] = safe_divide(
        grouped["errores_forzados_provocados"], grouped["total_golpes"], 100
    )

    return _round_numeric(grouped[config.PLAYER_METRIC_COLUMNS])


def compute_pair_match_metrics(actions: pd.DataFrame) -> pd.DataFrame:
    if actions.empty:
        return pd.DataFrame(columns=config.PAIR_METRIC_COLUMNS)

    group_cols = ["match_id", "tournament", "round", "pareja"]
    grouped = (
        actions.groupby(group_cols, dropna=False)
        .agg(
            total_golpes=("es_golpe", "sum"),
            winners=("es_winner", "sum"),
            errores_totales=("es_error", "sum"),
            errores_no_forzados=("es_error_no_forzado", "sum"),
            errores_forzados_provocados=("es_fuerza_error", "sum"),
        )
        .reset_index()
    )

    grouped["winner_pct"] = safe_divide(grouped["winners"], grouped["total_golpes"], 100)
    grouped["error_pct"] = safe_divide(grouped["errores_totales"], grouped["total_golpes"], 100)
    grouped["presion_ejercida_pct"] = safe_divide(
        grouped["errores_forzados_provocados"], grouped["total_golpes"], 100
    )

    return _round_numeric(grouped[config.PAIR_METRIC_COLUMNS])


def compute_player_global_metrics(player_match_metrics: pd.DataFrame) -> pd.DataFrame:
    if player_match_metrics.empty:
        return pd.DataFrame()

    grouped = (
        player_match_metrics.groupby(["jugador", "pareja"], dropna=False)
        .agg(
            partidos=("match_id", "nunique"),
            total_golpes=("total_golpes", "sum"),
            winners=("winners", "sum"),
            errores_totales=("errores_totales", "sum"),
            errores_no_forzados=("errores_no_forzados", "sum"),
            errores_forzados_provocados=("errores_forzados_provocados", "sum"),
            servicios=("servicios", "sum"),
        )
        .reset_index()
    )
    grouped["winner_pct"] = safe_divide(grouped["winners"], grouped["total_golpes"], 100)
    grouped["error_pct"] = safe_divide(grouped["errores_totales"], grouped["total_golpes"], 100)
    grouped["indice_riesgo"] = safe_divide(grouped["errores_no_forzados"], grouped["errores_totales"])
    grouped["efectividad_ofensiva"] = safe_divide(grouped["winners"], grouped["errores_no_forzados"])
    grouped["presion_ejercida_pct"] = safe_divide(
        grouped["errores_forzados_provocados"], grouped["total_golpes"], 100
    )
    return _round_numeric(grouped.sort_values("total_golpes", ascending=False))


def compute_pair_global_metrics(pair_match_metrics: pd.DataFrame) -> pd.DataFrame:
    if pair_match_metrics.empty:
        return pd.DataFrame()

    grouped = (
        pair_match_metrics.groupby(["pareja"], dropna=False)
        .agg(
            partidos=("match_id", "nunique"),
            total_golpes=("total_golpes", "sum"),
            winners=("winners", "sum"),
            errores_totales=("errores_totales", "sum"),
            errores_no_forzados=("errores_no_forzados", "sum"),
        )
        .reset_index()
    )
    grouped["winner_pct"] = safe_divide(grouped["winners"], grouped["total_golpes"], 100)
    grouped["error_pct"] = safe_divide(grouped["errores_totales"], grouped["total_golpes"], 100)
    grouped["presion_ejercida_pct"] = np.nan
    if "presion_ejercida_pct" in pair_match_metrics.columns:
        pressure_counts = pair_match_metrics.assign(
            errores_forzados_provocados=lambda df: (
                pd.to_numeric(df["presion_ejercida_pct"], errors="coerce")
                * pd.to_numeric(df["total_golpes"], errors="coerce")
                / 100
            )
        )
        pressure = pressure_counts.groupby("pareja", dropna=False)["errores_forzados_provocados"].sum()
        grouped["presion_ejercida_pct"] = safe_divide(
            grouped["pareja"].map(pressure), grouped["total_golpes"], 100
        )
    return _round_numeric(grouped.sort_values("total_golpes", ascending=False))

