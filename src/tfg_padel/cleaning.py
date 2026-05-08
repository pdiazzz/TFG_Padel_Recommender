from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

import pandas as pd


NULL_STRINGS = {"", "nan", "none", "null", "na", "n/a", "<na>"}

COLUMN_RENAMES = {
    "fuerza_error": "fuerza_error",
    "fuerzaerror": "fuerza_error",
    "punto_win": "punto_win",
    "punto_lost": "punto_lost",
    "break_point": "break_point",
    "match_point": "match_point",
    "set_point": "set_point",
    "set_num": "set_num",
    "set_p1": "set_p1",
    "set_p2": "set_p2",
    "juego_p1": "juego_p1",
    "juego_p2": "juego_p2",
    "punto_p1": "punto_p1",
    "punto_p2": "punto_p2",
    "golpe_q": "golpe_q",
    "cara_pala": "cara_pala",
    "zona_saque": "zona_saque",
    "zona_resto": "zona_resto",
    "clip_start": "clip_start",
    "clip_end": "clip_end",
    "row_name": "row_name",
}

COORDINATE_ALIASES = {
    "inicio_gople_x": "inicio_x",
    "inicio_golpe_x": "inicio_x",
    "golpe_inicio_x": "inicio_x",
    "start_x": "inicio_x",
    "inicio_gople_y": "inicio_y",
    "inicio_golpe_y": "inicio_y",
    "golpe_inicio_y": "inicio_y",
    "start_y": "inicio_y",
    "fin_gople_x": "fin_x",
    "fin_golpe_x": "fin_x",
    "golpe_fin_x": "fin_x",
    "end_x": "fin_x",
    "fin_gople_y": "fin_y",
    "fin_golpe_y": "fin_y",
    "golpe_fin_y": "fin_y",
    "end_y": "fin_y",
}


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_column_name(column: object) -> str:
    """Convert raw M3 column names to stable snake_case names."""
    text = str(column).strip()
    text = strip_accents(text)
    text = text.replace("º", "o").replace("ª", "a")
    text = text.lower()
    text = re.sub(r"[:/\\()\[\]{}]+", "_", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return COLUMN_RENAMES.get(text, text)


def is_empty_like(series: pd.Series) -> pd.Series:
    return series.isna() | series.astype("string").str.strip().str.lower().isin(NULL_STRINGS)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize and coalesce duplicated column names after snake_case conversion."""
    out = pd.DataFrame(index=df.index)

    for idx, original in enumerate(df.columns):
        new_name = normalize_column_name(original)
        series = df.iloc[:, idx]
        if new_name not in out.columns:
            out[new_name] = series
            continue

        current_empty = is_empty_like(out[new_name])
        candidate_not_empty = ~is_empty_like(series)
        out.loc[current_empty & candidate_not_empty, new_name] = series.loc[
            current_empty & candidate_not_empty
        ]

    return out


def coalesce_aliases(df: pd.DataFrame, aliases: dict[str, str]) -> pd.DataFrame:
    """Merge alias columns into canonical columns using first non-empty value."""
    df = df.copy()
    for alias, canonical in aliases.items():
        if alias not in df.columns:
            continue
        if canonical not in df.columns:
            df[canonical] = df[alias]
        else:
            current_empty = is_empty_like(df[canonical])
            alias_not_empty = ~is_empty_like(df[alias])
            df.loc[current_empty & alias_not_empty, canonical] = df.loc[
                current_empty & alias_not_empty, alias
            ]
        if alias != canonical:
            df = df.drop(columns=[alias])
    return df


def clean_string_values(df: pd.DataFrame) -> pd.DataFrame:
    """Trim strings and convert empty/null-like strings to pandas NA."""
    df = df.copy()
    for column in df.columns:
        if pd.api.types.is_object_dtype(df[column]) or pd.api.types.is_string_dtype(df[column]):
            values = df[column].astype("string").str.strip()
            values = values.mask(values.str.lower().isin(NULL_STRINGS), pd.NA)
            df[column] = values
    return df


def first_non_empty(series: pd.Series):
    values = series[~is_empty_like(series)]
    return values.iloc[0] if len(values) else pd.NA


def collapse_events(df: pd.DataFrame) -> tuple[pd.DataFrame, int, list[str]]:
    """Collapse multiple rows from the same tagged event inside each match."""
    keys = [c for c in ["match_id", "row_name", "clip_start", "clip_end"] if c in df.columns]
    warnings: list[str] = []

    if len(keys) < 4:
        warnings.append(
            "No se pudo colapsar por evento completo: faltan columnas clave "
            f"{sorted(set(['match_id', 'row_name', 'clip_start', 'clip_end']) - set(keys))}."
        )
        before = len(df)
        out = df.drop_duplicates().reset_index(drop=True)
        return out, before - len(out), warnings

    before = len(df)
    out = df.groupby(keys, as_index=False, sort=False, dropna=False).first()
    return out.reset_index(drop=True), before - len(out), warnings


def infer_pair_from_player(player: object, pair_1: object, pair_2: object) -> str | pd._libs.missing.NAType:
    if pd.isna(player):
        return pd.NA

    player_norm = strip_accents(str(player)).lower()
    for pair in [pair_1, pair_2]:
        if pd.isna(pair):
            continue
        pair_text = str(pair)
        names = [strip_accents(part).lower().strip() for part in pair_text.split("-")]
        tokens = {token for name in names for token in name.split() if len(token) >= 3}
        if any(token in player_norm for token in tokens):
            return pair_text
    return pd.NA


def fill_pair_values(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing pair labels from player modes and metadata pair names."""
    df = df.copy()
    if "pareja" not in df.columns:
        df["pareja"] = pd.NA

    if {"match_id", "jugador", "pareja"}.issubset(df.columns):
        known = df.dropna(subset=["jugador", "pareja"])
        mode_map: dict[tuple[str, str], str] = {}
        for (match_id, player), group in known.groupby(["match_id", "jugador"], dropna=False):
            modes = group["pareja"].dropna().mode()
            if len(modes):
                mode_map[(str(match_id), str(player))] = str(modes.iloc[0])

        missing_pair = is_empty_like(df["pareja"]) & ~is_empty_like(df["jugador"])
        for idx in df[missing_pair].index:
            key = (str(df.at[idx, "match_id"]), str(df.at[idx, "jugador"]))
            if key in mode_map:
                df.at[idx, "pareja"] = mode_map[key]

    required = {"jugador", "pair_1", "pair_2", "pareja"}
    if required.issubset(df.columns):
        missing_pair = is_empty_like(df["pareja"]) & ~is_empty_like(df["jugador"])
        for idx in df[missing_pair].index:
            df.at[idx, "pareja"] = infer_pair_from_player(
                df.at[idx, "jugador"], df.at[idx, "pair_1"], df.at[idx, "pair_2"]
            )

    return df


def normalize_and_clean(df: pd.DataFrame) -> pd.DataFrame:
    df = normalize_columns(df)
    df = coalesce_aliases(df, COORDINATE_ALIASES)
    df = clean_string_values(df)
    df = fill_pair_values(df)
    for column in ["inicio_x", "inicio_y", "fin_x", "fin_y"]:
        if column not in df.columns:
            df[column] = pd.NA
    return df.convert_dtypes()


def existing_columns(df: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    return [column for column in columns if column in df.columns]
