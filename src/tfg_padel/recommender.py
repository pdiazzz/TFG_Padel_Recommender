from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


LIMITATION_TEXT = (
    "Orientación heurística basada en métricas agregadas del partido. "
    "No incorpora vídeo, marcador contextual, estado físico ni instrucciones tácticas previas."
)

RULE_DOCUMENTATION = [
    {
        "rule_applied": "player_error_pct_above_match_mean",
        "condition": "El error_pct del jugador es superior a la media de error_pct de los jugadores del mismo partido.",
        "recommendation_type": "Aumentar la presión o el volumen de juego sobre ese jugador, siempre con cautela contextual.",
    },
    {
        "rule_applied": "high_offensive_efficiency_low_error",
        "condition": "La efectividad_ofensiva del jugador es igual o superior a la mediana del partido y su error_pct no supera la media del partido.",
        "recommendation_type": "Evitar concederle bolas cómodas de finalización.",
    },
    {
        "rule_applied": "high_winner_high_error",
        "condition": "El jugador supera simultáneamente la media del partido en winner_pct y error_pct.",
        "recommendation_type": "Limitar sus situaciones de ataque directo y buscar contextos que aumenten su toma de riesgo.",
    },
    {
        "rule_applied": "high_volume_low_winner",
        "condition": "El jugador supera la mediana de total_golpes del partido y queda por debajo de la media de winner_pct.",
        "recommendation_type": "Interpretarlo como posible constructor del punto más que como finalizador principal.",
    },
    {
        "rule_applied": "pair_error_pct_above_rival",
        "condition": "La pareja tiene error_pct agregado superior al de la pareja rival en el mismo partido.",
        "recommendation_type": "Priorizar patrones de intercambio que mantengan presión sostenida sobre la pareja rival y favorezcan la aparición de errores no forzados, evitando asumir riesgos innecesarios en fases neutras del punto.",
    },
    {
        "rule_applied": "no_recommendation_due_to_insufficient_evidence",
        "condition": "Faltan métricas suficientes o ninguna regla encuentra diferencias claras.",
        "recommendation_type": "No se genera orientación táctica; se documenta la falta de evidencia.",
    },
]


def _row(
    match_id: str,
    scope: str,
    target: str,
    evidence_metric: str,
    evidence_value: object,
    rule_applied: str,
    recommendation: str,
    justification: str,
    limitations: str = LIMITATION_TEXT,
) -> dict[str, object]:
    return {
        "match_id": match_id,
        "scope": scope,
        "target": target,
        "evidence_metric": evidence_metric,
        "evidence_value": evidence_value,
        "rule_applied": rule_applied,
        "recommendation": recommendation,
        "justification": justification,
        "limitations": limitations,
    }


def _finite_mean(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return float(values.mean()) if len(values) else np.nan


def generate_recommendations(
    player_metrics: pd.DataFrame, pair_metrics: pd.DataFrame
) -> pd.DataFrame:
    recommendations: list[dict[str, object]] = []

    if player_metrics.empty:
        return pd.DataFrame(
            [
                _row(
                    "all",
                    "dataset",
                    "all",
                    "insufficient_evidence",
                    np.nan,
                    "no_recommendation_due_to_insufficient_evidence",
                    "no_recommendation_due_to_insufficient_evidence",
                    "No hay métricas jugador-partido disponibles.",
                    "El pipeline no dispone de evidencia suficiente.",
                )
            ],
            columns=config.RECOMMENDATION_COLUMNS,
        )

    for match_id, match_players in player_metrics.groupby("match_id", dropna=False):
        match_id = str(match_id)
        if len(match_players) < 2:
            recommendations.append(
                _row(
                    match_id,
                    "match",
                    match_id,
                    "insufficient_evidence",
                    np.nan,
                    "no_recommendation_due_to_insufficient_evidence",
                    "no_recommendation_due_to_insufficient_evidence",
                    "Menos de dos jugadores con métricas disponibles.",
                    "No se fuerza una conclusion tactica con muestra insuficiente.",
                )
            )
            continue

        mean_error = _finite_mean(match_players["error_pct"])
        mean_winner = _finite_mean(match_players["winner_pct"])
        median_total = _finite_mean(match_players["total_golpes"])
        finite_eff = pd.to_numeric(match_players["efectividad_ofensiva"], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        )
        median_eff = float(finite_eff.dropna().median()) if finite_eff.notna().any() else np.nan

        before_count = len(recommendations)
        for _, player in match_players.iterrows():
            target = str(player["jugador"])
            error_pct = float(player["error_pct"]) if pd.notna(player["error_pct"]) else np.nan
            winner_pct = float(player["winner_pct"]) if pd.notna(player["winner_pct"]) else np.nan
            total_golpes = float(player["total_golpes"]) if pd.notna(player["total_golpes"]) else np.nan
            eff = (
                float(player["efectividad_ofensiva"])
                if pd.notna(player["efectividad_ofensiva"])
                else np.nan
            )

            if pd.notna(error_pct) and pd.notna(mean_error) and error_pct > mean_error:
                recommendations.append(
                    _row(
                        match_id,
                        "player",
                        target,
                        "error_pct",
                        round(error_pct, 4),
                        "player_error_pct_above_match_mean",
                        "Aumentar la presión o el volumen de juego sobre este jugador con cautela contextual.",
                        f"{target} tiene error_pct={error_pct:.2f}, por encima de la media del partido ({mean_error:.2f}).",
                    )
                )

            if (
                pd.notna(eff)
                and pd.notna(median_eff)
                and pd.notna(error_pct)
                and pd.notna(mean_error)
                and eff >= median_eff
                and error_pct <= mean_error
            ):
                recommendations.append(
                    _row(
                        match_id,
                        "player",
                        target,
                        "efectividad_ofensiva",
                        round(eff, 4),
                        "high_offensive_efficiency_low_error",
                        "Evitar concederle bolas cómodas de finalización.",
                        f"{target} combina efectividad_ofensiva={eff:.2f} con error_pct={error_pct:.2f}, no superior a la media del partido.",
                    )
                )

            if (
                pd.notna(winner_pct)
                and pd.notna(error_pct)
                and pd.notna(mean_winner)
                and pd.notna(mean_error)
                and winner_pct > mean_winner
                and error_pct > mean_error
            ):
                recommendations.append(
                    _row(
                        match_id,
                        "player",
                        target,
                        "winner_pct_and_error_pct",
                        f"{winner_pct:.4f};{error_pct:.4f}",
                        "high_winner_high_error",
                        "Limitar sus situaciones de ataque directo y buscar contextos que aumenten su toma de riesgo.",
                        f"{target} supera la media del partido en winner_pct ({winner_pct:.2f}) y error_pct ({error_pct:.2f}).",
                    )
                )

            if (
                pd.notna(total_golpes)
                and pd.notna(winner_pct)
                and pd.notna(median_total)
                and pd.notna(mean_winner)
                and total_golpes > median_total
                and winner_pct < mean_winner
            ):
                recommendations.append(
                    _row(
                        match_id,
                        "player",
                        target,
                        "total_golpes_and_winner_pct",
                        f"{total_golpes:.0f};{winner_pct:.4f}",
                        "high_volume_low_winner",
                        "Interpretarlo como posible constructor del punto más que como finalizador principal.",
                        f"{target} supera la mediana de volumen del partido ({median_total:.0f}) y queda por debajo de la media de winner_pct ({mean_winner:.2f}).",
                    )
                )

        match_pairs = pair_metrics[pair_metrics["match_id"].astype(str) == match_id].copy()
        match_pairs["error_pct"] = pd.to_numeric(match_pairs["error_pct"], errors="coerce")
        if len(match_pairs.dropna(subset=["error_pct"])) >= 2:
            max_error = match_pairs["error_pct"].max()
            min_error = match_pairs["error_pct"].min()
            for _, pair in match_pairs[match_pairs["error_pct"] == max_error].iterrows():
                if pd.notna(max_error) and max_error > min_error:
                    target = str(pair["pareja"])
                    recommendations.append(
                        _row(
                            match_id,
                            "pair",
                            target,
                            "pair_error_pct_vs_rival",
                            round(float(max_error), 4),
                            "pair_error_pct_above_rival",
                            "Priorizar patrones de intercambio que mantengan presión sostenida sobre la pareja rival y favorezcan la aparición de errores no forzados, evitando asumir riesgos innecesarios en fases neutras del punto.",
                            f"{target} presenta error_pct agregado={max_error:.2f}, superior al rival ({min_error:.2f}).",
                        )
                    )

        if len(recommendations) == before_count:
            recommendations.append(
                _row(
                    match_id,
                    "match",
                    match_id,
                    "insufficient_evidence",
                    np.nan,
                    "no_recommendation_due_to_insufficient_evidence",
                    "no_recommendation_due_to_insufficient_evidence",
                    "Las reglas no encontraron diferencias suficientemente claras con las métricas disponibles.",
                    "No se fuerza una orientación cuando la evidencia relativa no activa ninguna regla.",
                )
            )

    return pd.DataFrame(recommendations, columns=config.RECOMMENDATION_COLUMNS)
