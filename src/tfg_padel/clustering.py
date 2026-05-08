from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from . import config


def _empty_outputs(message: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    scores = pd.DataFrame(
        [{"k": pd.NA, "inertia": pd.NA, "silhouette": pd.NA, "recommended": False, "warning": message}]
    )
    clusters = pd.DataFrame(columns=["match_id", "jugador", "pareja", "cluster"])
    profiles = pd.DataFrame(columns=["cluster", "n_observations", "profile_interpretation"])
    return scores, clusters, profiles, [message]


def _prepare_features(player_metrics: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_cols = ["match_id", "tournament", "round", "jugador", "pareja"]
    cols = [column for column in config.CLUSTER_FEATURE_COLUMNS if column in player_metrics.columns]
    data = player_metrics[base_cols + cols].copy()
    data[cols] = data[cols].apply(pd.to_numeric, errors="coerce")
    data = data.dropna(subset=cols, how="all").reset_index(drop=True)
    if data.empty:
        return data, pd.DataFrame(columns=cols)
    feature_data = data[cols].copy()
    feature_data = feature_data.fillna(feature_data.median(numeric_only=True))
    feature_data = feature_data.fillna(0)
    return data, feature_data


def choose_recommended_k(scores: pd.DataFrame) -> int | None:
    valid = scores.dropna(subset=["silhouette"]).copy()
    if valid.empty:
        valid = scores.dropna(subset=["inertia"]).copy()
        return int(valid["k"].min()) if not valid.empty else None

    best = valid["silhouette"].max()
    near_best = valid[valid["silhouette"] >= best - 0.03]
    return int(near_best["k"].min())


def _interpret_profile(row: pd.Series, global_means: pd.Series) -> str:
    winner_high = row.get("winner_pct", 0) >= global_means.get("winner_pct", 0)
    error_high = row.get("error_pct", 0) >= global_means.get("error_pct", 0)
    pressure_high = row.get("presion_ejercida_pct", 0) >= global_means.get("presion_ejercida_pct", 0)

    if winner_high and not error_high:
        return "perfil ofensivo eficiente relativo a la muestra"
    if winner_high and error_high:
        return "perfil ofensivo de mayor riesgo relativo"
    if pressure_high and not winner_high:
        return "perfil de presion indirecta relativo"
    if not winner_high and not error_high:
        return "perfil de continuidad/control relativo"
    return "perfil con errores por encima de la media relativa"


def run_player_match_clustering(
    player_metrics: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    warnings: list[str] = []
    if player_metrics.empty:
        return _empty_outputs("No hay metricas jugador-partido para clustering.")

    players, features = _prepare_features(player_metrics)
    n_observations = len(features)
    if n_observations < 3:
        return _empty_outputs(
            f"No hay observaciones suficientes para clustering jugador-partido (n={n_observations})."
        )

    scaler = StandardScaler()
    scaled = scaler.fit_transform(features)
    max_k = min(6, n_observations - 1)
    score_rows: list[dict[str, object]] = []

    for k in range(2, max_k + 1):
        model = KMeans(n_clusters=k, random_state=config.RANDOM_STATE, n_init=20)
        labels = model.fit_predict(scaled)
        silhouette = np.nan
        if len(set(labels)) > 1 and len(set(labels)) < n_observations:
            silhouette = float(silhouette_score(scaled, labels))
        score_rows.append(
            {
                "k": k,
                "inertia": float(model.inertia_),
                "silhouette": silhouette,
                "recommended": False,
                "warning": "",
            }
        )

    scores = pd.DataFrame(score_rows)
    recommended_k = choose_recommended_k(scores)
    if recommended_k is None:
        return _empty_outputs("No se pudo seleccionar un k para clustering.")

    if n_observations / recommended_k < 3:
        warnings.append(
            "El k recomendado genera clusters con pocas observaciones medias; interpretar con cautela."
        )

    silhouette_value = scores.loc[scores["k"] == recommended_k, "silhouette"].iloc[0]
    if pd.notna(silhouette_value) and silhouette_value < 0.15:
        warnings.append(
            "Silhouette bajo para el k recomendado; el clustering se usa solo como apoyo descriptivo."
        )

    scores.loc[scores["k"] == recommended_k, "recommended"] = True
    if warnings:
        scores.loc[scores["k"] == recommended_k, "warning"] = " | ".join(warnings)

    final_model = KMeans(n_clusters=recommended_k, random_state=config.RANDOM_STATE, n_init=20)
    players = players.copy()
    players["cluster"] = final_model.fit_predict(scaled)

    clusters = player_metrics.merge(
        players[["match_id", "jugador", "pareja", "cluster"]],
        on=["match_id", "jugador", "pareja"],
        how="left",
    )

    profile_metrics = [c for c in config.CLUSTER_FEATURE_COLUMNS if c in clusters.columns]
    profiles = (
        clusters.dropna(subset=["cluster"])
        .groupby("cluster")
        .agg(n_observations=("match_id", "size"), **{c: (c, "mean") for c in profile_metrics})
        .reset_index()
    )
    global_means = clusters[profile_metrics].mean(numeric_only=True)
    if not profiles.empty:
        profiles["profile_interpretation"] = profiles.apply(
            lambda row: _interpret_profile(row, global_means), axis=1
        )
        numeric_cols = profiles.select_dtypes(include=["number"]).columns
        profiles[numeric_cols] = profiles[numeric_cols].round(4)

    return scores.round(4), clusters, profiles, warnings

