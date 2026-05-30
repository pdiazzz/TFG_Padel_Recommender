from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
import re

import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from . import config
from .io import load_matches_metadata, read_csv_if_exists, write_csv
from .recommendations_reporting import PdfWriter, _write_pdf_with_fallback


DEFAULT_K_NEIGHBORS = 3
METHOD_NAME = "content_based_knn"
LIMITATION_TEXT = (
    "Orientación exploratoria basada en similitud de métricas jugador-partido; "
    "no validada con expertos ni interpretable como acción óptima."
)

CANDIDATE_FEATURES = [
    "winner_pct",
    "error_pct",
    "indice_riesgo",
    "efectividad_ofensiva",
    "presion_ejercida_pct",
    "total_golpes",
]

NEIGHBOR_COLUMNS = [
    "target_match_id",
    "target_match_label",
    "target_player",
    "neighbor_rank",
    "neighbor_match_id",
    "neighbor_match_label",
    "neighbor_player",
    "similarity",
    "neighbor_profile",
    "neighbor_main_recommendation",
]

RECOMMENDATION_COLUMNS = [
    "match_id",
    "match_label",
    "player",
    "recommended_profile",
    "recommended_action",
    "evidence",
    "neighbors_used",
    "mean_similarity",
    "method",
    "limitations",
]

DIAGNOSTIC_COLUMNS = [
    "num_targets",
    "num_recommendations",
    "mean_similarity",
    "min_similarity",
    "max_similarity",
    "coverage_pct",
    "players_covered",
    "matches_covered",
    "k_neighbors",
    "overlap_with_heuristic_pct",
]

FEATURE_LABELS = {
    "winner_pct": "Winner%",
    "error_pct": "Error%",
    "indice_riesgo": "Índice de riesgo",
    "efectividad_ofensiva": "Efectividad ofensiva",
    "presion_ejercida_pct": "Presión ejercida%",
    "total_golpes": "Golpes",
}


def load_player_match_metrics(path: Path | None = None) -> pd.DataFrame:
    """Load player-match metrics used by the content-based line."""
    path = path or (config.PROCESSED_DIR / "player_match_metrics.csv")
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}. Ejecuta primero: python scripts/run_pipeline.py"
        )
    df = read_csv_if_exists(path)
    required = {"match_id", "jugador"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"player_match_metrics.csv no contiene columnas obligatorias: {missing}")
    if df.empty:
        raise ValueError("player_match_metrics.csv existe, pero está vacío.")
    return df


def _year_from_match_id(match_id: str) -> str:
    match = re.search(r"(20\d{2})", match_id)
    return match.group(1) if match else ""


def _clean_pair_label(value: object) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    return text.replace(" - ", "/").replace(" / ", "/")


def _fallback_match_label(match_id: str) -> str:
    text = match_id.replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else match_id


def build_match_labels() -> dict[str, str]:
    """Build readable match labels from metadata when available."""
    try:
        metadata = load_matches_metadata()
    except (FileNotFoundError, ValueError):
        return {}

    labels: dict[str, str] = {}
    for _, row in metadata.iterrows():
        match_id = str(row["match_id"])
        tournament = str(row["tournament"]).strip()
        year = _year_from_match_id(match_id)
        round_name = str(row["round"]).strip()
        pair_1 = _clean_pair_label(row["pair_1"])
        pair_2 = _clean_pair_label(row["pair_2"])
        heading = f"{tournament} {year}".strip()
        parts = [heading]
        if round_name and round_name != "pending_review":
            parts.append(round_name)
        label = " - ".join(part for part in parts if part)
        if pair_1 and pair_2:
            label = f"{label} - {pair_1} vs {pair_2}" if label else f"{pair_1} vs {pair_2}"
        labels[match_id] = label or _fallback_match_label(match_id)
    return labels


def get_recommender_features(df: pd.DataFrame) -> list[str]:
    """Select numeric features available with enough variation for cosine similarity."""
    features: list[str] = []
    for column in CANDIDATE_FEATURES:
        if column not in df.columns:
            continue
        values = pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan)
        finite = values.dropna()
        if len(finite) >= 2 and finite.nunique() > 1:
            features.append(column)
    if not features:
        raise ValueError(
            "No hay variables numéricas suficientes para la línea base basada en contenido."
        )
    return features


def prepare_feature_matrix(df: pd.DataFrame, feature_cols: list[str]) -> tuple[np.ndarray, pd.DataFrame]:
    """Impute missing values with medians and standardize features."""
    if not feature_cols:
        raise ValueError("feature_cols no puede estar vacío.")
    numeric = df[feature_cols].apply(pd.to_numeric, errors="coerce")
    numeric = numeric.replace([np.inf, -np.inf], np.nan)
    medians = numeric.median(numeric_only=True).fillna(0.0)
    prepared = numeric.fillna(medians).fillna(0.0)
    scaler = StandardScaler()
    matrix = scaler.fit_transform(prepared)
    return matrix, prepared


def compute_similarity_matrix(X: np.ndarray) -> np.ndarray:
    """Compute cosine similarity between standardized player-match vectors."""
    if X.ndim != 2:
        raise ValueError("X debe ser una matriz bidimensional.")
    if X.shape[0] == 0:
        return np.empty((0, 0))
    similarity = cosine_similarity(X)
    return np.nan_to_num(similarity, nan=0.0, posinf=0.0, neginf=0.0)


def _load_recommendation_cards(path: Path | None = None) -> pd.DataFrame:
    path = path or config.PLAYER_RECOMMENDATION_CARDS_PATH
    cards = read_csv_if_exists(path)
    if cards.empty:
        return pd.DataFrame()
    required = {"match_id", "player"}
    if not required.issubset(cards.columns):
        return pd.DataFrame()
    return cards


def _enrich_metrics(metrics: pd.DataFrame, cards: pd.DataFrame | None = None) -> pd.DataFrame:
    labels = build_match_labels()
    out = metrics.copy().reset_index(drop=True)
    out["observation_id"] = range(len(out))
    out["match_id"] = out["match_id"].astype(str)
    out["jugador"] = out["jugador"].astype(str)
    out["match_label"] = out["match_id"].map(labels).fillna(out["match_id"].map(_fallback_match_label))

    cards = cards if cards is not None else _load_recommendation_cards()
    if cards.empty:
        out["player_profile"] = ""
        out["main_recommendation"] = ""
        out["priority_label"] = ""
        out["rules_triggered"] = ""
        return out

    card_cols = [
        column
        for column in [
            "match_id",
            "player",
            "match_label",
            "player_profile",
            "main_recommendation",
            "priority_label",
            "rules_triggered",
        ]
        if column in cards.columns
    ]
    card_subset = cards[card_cols].drop_duplicates(subset=["match_id", "player"]).copy()
    card_subset = card_subset.rename(columns={"player": "jugador", "match_label": "card_match_label"})
    out = out.merge(card_subset, on=["match_id", "jugador"], how="left")
    if "card_match_label" in out.columns:
        out["match_label"] = out["card_match_label"].fillna(out["match_label"])
        out = out.drop(columns=["card_match_label"])
    for column in ["player_profile", "main_recommendation", "priority_label", "rules_triggered"]:
        if column not in out.columns:
            out[column] = ""
        out[column] = out[column].fillna("")
    return out


def get_top_k_neighbors(
    df: pd.DataFrame,
    similarity_matrix: np.ndarray,
    k: int = DEFAULT_K_NEIGHBORS,
) -> pd.DataFrame:
    """Return the top-k most similar player-match neighbors for each observation."""
    if k <= 0:
        raise ValueError("k debe ser mayor que cero.")
    if len(df) != similarity_matrix.shape[0]:
        raise ValueError("La matriz de similitud no coincide con el número de observaciones.")
    if len(df) < 2:
        return pd.DataFrame(columns=NEIGHBOR_COLUMNS)

    rows: list[dict[str, object]] = []
    for target_pos, target in df.reset_index(drop=True).iterrows():
        similarities = similarity_matrix[target_pos].copy()
        similarities[target_pos] = -np.inf
        valid_positions = np.where(np.isfinite(similarities))[0]
        sorted_positions = valid_positions[np.argsort(similarities[valid_positions])[::-1]]
        for rank, neighbor_pos in enumerate(sorted_positions[: min(k, len(sorted_positions))], start=1):
            neighbor = df.iloc[int(neighbor_pos)]
            rows.append(
                {
                    "target_match_id": target["match_id"],
                    "target_match_label": target.get("match_label", ""),
                    "target_player": target["jugador"],
                    "neighbor_rank": rank,
                    "neighbor_match_id": neighbor["match_id"],
                    "neighbor_match_label": neighbor.get("match_label", ""),
                    "neighbor_player": neighbor["jugador"],
                    "similarity": round(float(similarities[neighbor_pos]), 4),
                    "neighbor_profile": neighbor.get("player_profile", ""),
                    "neighbor_main_recommendation": neighbor.get("main_recommendation", ""),
                }
            )
    return pd.DataFrame(rows, columns=NEIGHBOR_COLUMNS)


def _safe_mode(values: list[str]) -> str:
    clean = [value.strip() for value in values if isinstance(value, str) and value.strip()]
    if not clean:
        return ""
    return Counter(clean).most_common(1)[0][0]


def _metric(value: object) -> float:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(number) if pd.notna(number) else np.nan


def _fallback_recommendation(row: pd.Series, all_metrics: pd.DataFrame) -> tuple[str, str, str]:
    match_metrics = all_metrics[all_metrics["match_id"] == row["match_id"]]
    error_pct = _metric(row.get("error_pct"))
    winner_pct = _metric(row.get("winner_pct"))
    total_golpes = _metric(row.get("total_golpes"))

    mean_error = pd.to_numeric(match_metrics.get("error_pct"), errors="coerce").mean()
    mean_winner = pd.to_numeric(match_metrics.get("winner_pct"), errors="coerce").mean()
    median_volume = pd.to_numeric(match_metrics.get("total_golpes"), errors="coerce").median()

    high_error = pd.notna(error_pct) and pd.notna(mean_error) and error_pct > mean_error
    high_winner = pd.notna(winner_pct) and pd.notna(mean_winner) and winner_pct > mean_winner
    low_error = pd.notna(error_pct) and pd.notna(mean_error) and error_pct <= mean_error
    high_volume = pd.notna(total_golpes) and pd.notna(median_volume) and total_golpes > median_volume
    low_winner = pd.notna(winner_pct) and pd.notna(mean_winner) and winner_pct < mean_winner

    evidence = (
        f"Fallback métrico: Error%={error_pct:.2f}, Winner%={winner_pct:.2f}, "
        f"Golpes={total_golpes:.0f}; medias del partido Error%={mean_error:.2f}, "
        f"Winner%={mean_winner:.2f}."
    )
    if high_winner and high_error:
        return (
            "Atacante de alto riesgo",
            "Limitar situaciones cómodas de ataque directo y contrastar si el riesgo aparece bajo presión.",
            evidence,
        )
    if high_winner and low_error:
        return (
            "Finalizador eficiente",
            "Evitar concederle bolas cómodas de finalización y obligarle a atacar desde contextos menos favorables.",
            evidence,
        )
    if high_volume and low_winner:
        return (
            "Constructor del punto",
            "Interpretarlo como posible constructor o estabilizador del punto y variar ritmos para evitar que controle el intercambio.",
            evidence,
        )
    if high_error:
        return (
            "Foco potencial de presión",
            "Aumentar de forma prudente el volumen de juego sobre este jugador sin asumir riesgos innecesarios.",
            evidence,
        )
    return (
        "Sin evidencia suficiente",
        "No formular una orientación táctica fuerte sin evidencia adicional.",
        evidence,
    )


def _feature_list_text(feature_cols: list[str]) -> str:
    return ", ".join(FEATURE_LABELS.get(feature, feature) for feature in feature_cols)


def _neighbors_used_text(group: pd.DataFrame) -> str:
    parts: list[str] = []
    for _, row in group.sort_values("neighbor_rank").iterrows():
        parts.append(
            f"{row['neighbor_player']} ({row['neighbor_match_label']}, sim={float(row['similarity']):.2f})"
        )
    return "; ".join(parts)


def build_content_based_recommendations(
    enriched_metrics: pd.DataFrame,
    neighbors: pd.DataFrame,
    feature_cols: list[str],
) -> pd.DataFrame:
    """Build exploratory guidance from similar player-match observations."""
    rows: list[dict[str, object]] = []
    grouped_neighbors = {
        key: group.copy()
        for key, group in neighbors.groupby(["target_match_id", "target_player"], dropna=False)
    }
    feature_text = _feature_list_text(feature_cols)

    for _, target in enriched_metrics.iterrows():
        key = (target["match_id"], target["jugador"])
        group = grouped_neighbors.get(key, pd.DataFrame(columns=NEIGHBOR_COLUMNS))
        mean_similarity = float(group["similarity"].mean()) if not group.empty else np.nan

        profile = _safe_mode(group.get("neighbor_profile", pd.Series(dtype=str)).dropna().astype(str).tolist())
        action = _safe_mode(
            group.get("neighbor_main_recommendation", pd.Series(dtype=str)).dropna().astype(str).tolist()
        )
        fallback_profile, fallback_action, fallback_evidence = _fallback_recommendation(target, enriched_metrics)
        if not profile:
            profile = fallback_profile
        if not action:
            action = fallback_action

        if group.empty:
            evidence = f"{fallback_evidence} No hay vecinos suficientes; se usa la rama fallback."
            neighbors_used = ""
        else:
            evidence = (
                f"Basado en {len(group)} vecino(s) similares con similitud media={mean_similarity:.2f}. "
                f"Métricas usadas: {feature_text}. Perfil sugerido por vecinos: {profile}."
            )
            neighbors_used = _neighbors_used_text(group)

        rows.append(
            {
                "match_id": target["match_id"],
                "match_label": target["match_label"],
                "player": target["jugador"],
                "recommended_profile": profile,
                "recommended_action": action,
                "evidence": evidence,
                "neighbors_used": neighbors_used,
                "mean_similarity": round(mean_similarity, 4) if pd.notna(mean_similarity) else np.nan,
                "method": METHOD_NAME,
                "limitations": LIMITATION_TEXT,
            }
        )
    return pd.DataFrame(rows, columns=RECOMMENDATION_COLUMNS)


def build_diagnostics(
    recommendations: pd.DataFrame,
    neighbors: pd.DataFrame,
    enriched_metrics: pd.DataFrame,
    k_neighbors: int,
) -> pd.DataFrame:
    """Create exploratory diagnostics without pretending to estimate accuracy."""
    num_targets = len(enriched_metrics)
    num_recommendations = len(recommendations)
    similarities = pd.to_numeric(neighbors.get("similarity", pd.Series(dtype=float)), errors="coerce")
    coverage_pct = round(num_recommendations / num_targets * 100, 2) if num_targets else 0.0

    overlap = np.nan
    if "player_profile" in enriched_metrics.columns and not enriched_metrics["player_profile"].eq("").all():
        comparison = recommendations.merge(
            enriched_metrics[["match_id", "jugador", "player_profile"]].rename(columns={"jugador": "player"}),
            on=["match_id", "player"],
            how="inner",
        )
        comparison = comparison[comparison["player_profile"].astype(str).str.len() > 0]
        if not comparison.empty:
            overlap = round(
                (comparison["recommended_profile"] == comparison["player_profile"]).mean() * 100,
                2,
            )

    row = {
        "num_targets": num_targets,
        "num_recommendations": num_recommendations,
        "mean_similarity": round(float(similarities.mean()), 4) if similarities.notna().any() else np.nan,
        "min_similarity": round(float(similarities.min()), 4) if similarities.notna().any() else np.nan,
        "max_similarity": round(float(similarities.max()), 4) if similarities.notna().any() else np.nan,
        "coverage_pct": coverage_pct,
        "players_covered": recommendations["player"].nunique() if not recommendations.empty else 0,
        "matches_covered": recommendations["match_id"].nunique() if not recommendations.empty else 0,
        "k_neighbors": k_neighbors,
        "overlap_with_heuristic_pct": overlap,
    }
    return pd.DataFrame([row], columns=DIAGNOSTIC_COLUMNS)


def _write_summary_report(
    diagnostics: pd.DataFrame,
    recommendations: pd.DataFrame,
    neighbors: pd.DataFrame,
    feature_cols: list[str],
    k_neighbors: int,
) -> None:
    diag = diagnostics.iloc[0].to_dict() if not diagnostics.empty else {}
    num_targets = int(diag.get("num_targets", 0) or 0)
    num_recommendations = int(diag.get("num_recommendations", 0) or 0)
    players_covered = int(diag.get("players_covered", 0) or 0)
    matches_covered = int(diag.get("matches_covered", 0) or 0)
    profile_counts = recommendations["recommended_profile"].value_counts().to_dict()
    lines = [
        "# Resumen de la línea base basada en contenido",
        "",
        "Este informe resume una línea base exploratoria basada en similitud entre actuaciones jugador-partido.",
        "El método representa cada observación jugador-partido mediante métricas agregadas, normaliza las variables con `StandardScaler` y recupera vecinos mediante similitud coseno.",
        "",
        "## Configuración",
        "",
        f"- Método: `{METHOD_NAME}`",
        f"- Vecinos por objetivo: {k_neighbors}",
        f"- Métricas usadas: {_feature_list_text(feature_cols)}",
        "",
        "## Resultados",
        "",
        f"- Observaciones objetivo: {num_targets}",
        f"- Orientaciones generadas: {num_recommendations}",
        f"- Vecinos generados: {len(neighbors)}",
        f"- Similitud media: {diag.get('mean_similarity', np.nan)}",
        f"- Cobertura: {diag.get('coverage_pct', 0)} %",
        f"- Jugadores cubiertos: {players_covered}",
        f"- Partidos cubiertos: {matches_covered}",
        f"- Solapamiento con perfil heurístico existente: {diag.get('overlap_with_heuristic_pct', np.nan)} %",
        "",
        "## Perfiles sugeridos",
        "",
    ]
    if profile_counts:
        lines.extend([f"- {profile}: {count}" for profile, count in profile_counts.items()])
    else:
        lines.append("- No se generaron perfiles.")
    lines.extend(
        [
            "",
            "## Limitaciones",
            "",
            "- No hay feedback explícito de usuarios ni valoración de entrenadores.",
            "- No existe ground truth táctico; por tanto no se reportan accuracy, precision ni recall.",
            "- El método no predice la mejor acción ni sustituye el criterio del entrenador.",
            "- La muestra es reducida, por lo que la línea base debe interpretarse como apoyo exploratorio.",
            "- Las orientaciones se derivan de similitud entre actuaciones jugador-partido y de fichas heurísticas previas cuando están disponibles.",
            "",
        ]
    )
    config.CLASSICAL_RECOMMENDER_SUMMARY_PATH.write_text("\n".join(lines), encoding="utf-8")


def _write_memory_update(
    diagnostics: pd.DataFrame,
    feature_cols: list[str],
) -> None:
    diag = diagnostics.iloc[0].to_dict() if not diagnostics.empty else {}
    num_targets = int(diag.get("num_targets", 0) or 0)
    num_recommendations = int(diag.get("num_recommendations", 0) or 0)
    k_neighbors = int(diag.get("k_neighbors", 0) or 0)
    lines = [
        "# Actualización de memoria: línea base basada en contenido",
        "",
        "## Metodología",
        "",
        (
            "Como funcionalidad complementaria, se incorpora una línea base basada en contenido a nivel "
            "jugador-partido. Cada observación se representa mediante un vector de métricas agregadas "
            f"({ _feature_list_text(feature_cols) }), normalizado con `StandardScaler`, y se comparan las "
            "observaciones mediante similitud coseno. Para cada jugador en un partido se recuperan sus vecinos "
            "más similares y se infiere una orientación táctica a partir de los perfiles y orientaciones "
            "heurísticas presentes en esos vecinos."
        ),
        "",
        "## Descripción informática",
        "",
        (
            "La implementación se encapsula en `src/tfg_padel/classical_recommender.py` y se ejecuta mediante "
            "`python scripts/generate_classical_recommendations.py`. El módulo carga `player_match_metrics.csv`, "
            "selecciona variables numéricas disponibles, trata valores ausentes o infinitos, calcula similitudes "
            "coseno y exporta tablas reproducibles de vecinos, orientaciones y diagnósticos."
        ),
        "",
        "## Experimentación",
        "",
        (
            f"En la ejecución actual se generan {num_recommendations} orientaciones por similitud "
            f"sobre {num_targets} observaciones jugador-partido, con k={k_neighbors} "
            f"vecinos por objetivo y similitud media {diag.get('mean_similarity', np.nan)}. El resultado se usa "
            "como contraste exploratorio respecto a las fichas heurísticas, no como evaluación predictiva."
        ),
        "",
        "## Limitaciones",
        "",
        (
            "El algoritmo no es colaborativo porque no hay feedback explícito de usuarios ni interacciones "
            "entrenador-sistema. Tampoco existe validación con entrenadores ni una etiqueta de acción óptima; "
            "por ello no se reportan métricas como accuracy, precision o recall. Las salidas deben "
            "entenderse como orientaciones por similitud con actuaciones previas dentro de una muestra limitada."
        ),
        "",
        "## Tabla LaTeX opcional",
        "",
        r"\begin{tabularx}{\textwidth}{Xr}",
        r"\toprule",
        r"Indicador & Valor \\",
        r"\midrule",
        rf"Observaciones jugador-partido & {num_targets} \\",
        rf"Orientaciones por similitud & {num_recommendations} \\",
        rf"Vecinos por objetivo & {k_neighbors} \\",
        rf"Similitud media & {diag.get('mean_similarity', np.nan)} \\",
        rf"Cobertura & {diag.get('coverage_pct', 0)}\% \\",
        r"\bottomrule",
        r"\end{tabularx}",
        "",
    ]
    config.MEMORY_UPDATE_CLASSICAL_RECOMMENDER_PATH.write_text("\n".join(lines), encoding="utf-8")


def _diag_value(diagnostics: pd.DataFrame, column: str, default: object = "") -> object:
    if diagnostics.empty or column not in diagnostics.columns:
        return default
    value = diagnostics[column].iloc[0]
    return default if pd.isna(value) else value


def _add_classical_summary_page(
    writer: PdfWriter,
    diagnostics: pd.DataFrame,
    recommendations: pd.DataFrame,
    neighbors: pd.DataFrame,
    feature_cols: list[str],
    generated_at: datetime,
) -> None:
    writer.start_page("Línea base basada en contenido")
    writer.text("Informe explicativo de orientaciones por similitud jugador-partido", size=15, weight="bold")
    writer.field("Fecha de generación", f"{generated_at:%Y-%m-%d %H:%M}")
    writer.field("Método", METHOD_NAME)
    writer.field("Observaciones objetivo", int(_diag_value(diagnostics, "num_targets", 0)))
    writer.field("Orientaciones generadas", int(_diag_value(diagnostics, "num_recommendations", 0)))
    writer.field("Vecinos generados", len(neighbors))
    writer.field("Vecinos por objetivo", int(_diag_value(diagnostics, "k_neighbors", 0)))
    writer.field("Similitud media", _diag_value(diagnostics, "mean_similarity", ""))
    writer.field("Cobertura", f"{_diag_value(diagnostics, 'coverage_pct', '')}%")
    writer.field("Solapamiento con perfil heurístico", f"{_diag_value(diagnostics, 'overlap_with_heuristic_pct', '')}%")
    writer.field("Métricas usadas", _feature_list_text(feature_cols), width=88)
    writer.heading("Distribución de perfiles")
    for profile, count in recommendations["recommended_profile"].value_counts().items():
        writer.text(f"- {profile}: {count}", size=8.8)
    writer.heading("Lectura metodológica")
    writer.text(
        "Este informe presenta una línea base exploratoria basada en contenido. "
        "Las salidas son orientaciones tácticas interpretables basadas en métricas y similitud "
        "entre actuaciones jugador-partido; no predicen la mejor acción ni sustituyen al entrenador.",
        size=9,
    )


def _add_classical_method_page(writer: PdfWriter, feature_cols: list[str]) -> None:
    writer.start_page("Criterio de generación")
    writer.text(
        "Cada observación jugador-partido se representa mediante un vector de métricas agregadas. "
        "Las variables disponibles se imputan con medianas cuando es necesario, se normalizan con "
        "`StandardScaler` y se comparan mediante similitud coseno.",
        size=9.2,
    )
    writer.field("Métricas", _feature_list_text(feature_cols), width=88)
    writer.heading("Uso de vecinos")
    writer.text(
        "Para cada jugador se recuperan los k vecinos más similares, excluyendo la propia observación. "
        "Cuando los vecinos tienen ficha táctica heurística previa, el perfil y la orientación se infieren "
        "por frecuencia de esos vecinos. Si no hay ficha disponible, se usa una rama fallback métrica prudente.",
        size=9,
    )
    writer.heading("Limitaciones")
    writer.text(
        "No hay feedback explícito de usuarios ni validación con entrenadores. Tampoco existe una etiqueta de "
        "acción óptima, por lo que no se reportan métricas de accuracy, precision o recall. El método debe "
        "leerse como apoyo exploratorio por similitud, no como sistema autónomo de decisión.",
        size=9,
    )


def _add_classical_recommendation_pages(
    writer: PdfWriter,
    recommendations: pd.DataFrame,
    neighbors: pd.DataFrame,
) -> None:
    if recommendations.empty:
        writer.start_page("Orientaciones")
        writer.text("No se generaron orientaciones por similitud.", size=10)
        return

    neighbor_groups = {
        key: group.copy()
        for key, group in neighbors.groupby(["target_match_id", "target_player"], dropna=False)
    }
    for match_id, group in recommendations.groupby("match_id", sort=True):
        match_label = str(group["match_label"].iloc[0])
        writer.start_page(f"Partido: {match_label}")
        writer.field("match_id técnico", match_id)
        for _, row in group.sort_values(["recommended_profile", "player"]).iterrows():
            writer.ensure(9)
            writer.heading(str(row["player"]))
            writer.field("Perfil sugerido", row["recommended_profile"])
            writer.field("Similitud media", row["mean_similarity"])
            writer.field("Orientación sugerida", row["recommended_action"], width=88)
            writer.field("Evidencia", row["evidence"], width=88)
            key = (row["match_id"], row["player"])
            target_neighbors = neighbor_groups.get(key, pd.DataFrame(columns=NEIGHBOR_COLUMNS))
            if not target_neighbors.empty:
                writer.field("Vecinos usados", _neighbors_used_text(target_neighbors), width=88)
            writer.field("Limitaciones", row["limitations"], width=88)
            writer.spacer(0.012)


def _write_classical_pdf(
    path: Path,
    diagnostics: pd.DataFrame,
    recommendations: pd.DataFrame,
    neighbors: pd.DataFrame,
    feature_cols: list[str],
    generated_at: datetime,
) -> None:
    with PdfPages(path) as pdf:
        writer = PdfWriter(pdf)
        _add_classical_summary_page(writer, diagnostics, recommendations, neighbors, feature_cols, generated_at)
        _add_classical_method_page(writer, feature_cols)
        _add_classical_recommendation_pages(writer, recommendations, neighbors)
        writer.finish_page()


def run_content_based_recommender(k: int = DEFAULT_K_NEIGHBORS) -> dict[str, object]:
    """Run the content-based kNN line and export reproducible outputs."""
    config.ensure_directories()
    metrics = load_player_match_metrics()
    cards = _load_recommendation_cards()
    enriched = _enrich_metrics(metrics, cards)
    feature_cols = get_recommender_features(enriched)
    feature_matrix, _ = prepare_feature_matrix(enriched, feature_cols)
    similarity_matrix = compute_similarity_matrix(feature_matrix)
    neighbors = get_top_k_neighbors(enriched, similarity_matrix, k=k)
    recommendations = build_content_based_recommendations(enriched, neighbors, feature_cols)
    diagnostics = build_diagnostics(recommendations, neighbors, enriched, k)

    write_csv(neighbors, config.CLASSICAL_NEIGHBORS_PATH)
    write_csv(recommendations, config.CLASSICAL_RECOMMENDATIONS_PATH)
    write_csv(diagnostics, config.CLASSICAL_DIAGNOSTICS_PATH)
    _write_summary_report(diagnostics, recommendations, neighbors, feature_cols, k)
    _write_memory_update(diagnostics, feature_cols)
    classical_report_path, pdf_warning = _write_pdf_with_fallback(
        config.CLASSICAL_RECOMMENDER_REPORT_PATH,
        _write_classical_pdf,
        diagnostics,
        recommendations,
        neighbors,
        feature_cols,
        datetime.now(),
    )

    return {
        "neighbors": neighbors,
        "recommendations": recommendations,
        "diagnostics": diagnostics,
        "features": pd.DataFrame({"feature": feature_cols}),
        "classical_report_path": classical_report_path,
        "pdf_warnings": [pdf_warning] if pdf_warning else [],
    }
