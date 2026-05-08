from __future__ import annotations

import pandas as pd

from .cleaning import is_empty_like, strip_accents


FLAG_COLUMNS = [
    "es_golpe",
    "es_servicio",
    "es_winner",
    "es_error",
    "es_error_no_forzado",
    "es_missed",
    "es_fuerza_error",
    "es_punto_win",
    "es_punto_lost",
    "es_break_point",
]


def _normal_text(series: pd.Series) -> pd.Series:
    return (
        series.fillna("")
        .astype("string")
        .map(lambda value: strip_accents(str(value)).lower().strip())
    )


def _ensure_column(df: pd.DataFrame, column: str) -> None:
    if column not in df.columns:
        df[column] = pd.NA


def add_event_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Create reproducible boolean flags from the normalized event columns."""
    df = df.copy()
    for column in [
        "golpe_q",
        "servicio",
        "winner",
        "error",
        "fuerza_error",
        "punto_win",
        "punto_lost",
        "break_point",
    ]:
        _ensure_column(df, column)

    golpe = _normal_text(df["golpe_q"])
    servicio = _normal_text(df["servicio"])
    winner = _normal_text(df["winner"])
    error = _normal_text(df["error"])
    fuerza_error = _normal_text(df["fuerza_error"])
    break_point = _normal_text(df["break_point"])

    df["es_golpe"] = ~is_empty_like(df["golpe_q"])
    df["es_servicio"] = (~is_empty_like(df["servicio"])) | golpe.str.contains(
        r"\b(?:servicio|saque|service)\b", regex=True, na=False
    )
    df["es_winner"] = winner.str.contains("winner|ganador", regex=True, na=False)
    df["es_error_no_forzado"] = error.str.contains(
        "error no forzado|unforced", regex=True, na=False
    )
    df["es_missed"] = error.str.contains("missed|fallo|falla", regex=True, na=False)
    df["es_error"] = (~is_empty_like(df["error"])) | df["es_error_no_forzado"] | df["es_missed"]
    df["es_fuerza_error"] = fuerza_error.str.contains(
        "fuerza error|forced|forzado", regex=True, na=False
    ) | (~is_empty_like(df["fuerza_error"]))
    df["es_punto_win"] = ~is_empty_like(df["punto_win"])
    df["es_punto_lost"] = ~is_empty_like(df["punto_lost"])
    df["es_break_point"] = break_point.str.contains("break", regex=False, na=False) | (
        ~is_empty_like(df["break_point"])
    )

    for column in FLAG_COLUMNS:
        df[column] = df[column].fillna(False).astype(bool)

    return df


def get_analyzable_actions(df: pd.DataFrame) -> pd.DataFrame:
    """Return tagged shots/actions with an identified player."""
    if "jugador" not in df.columns:
        return df.iloc[0:0].copy()
    mask = df["es_golpe"] & ~is_empty_like(df["jugador"])
    return df.loc[mask].reset_index(drop=True)
