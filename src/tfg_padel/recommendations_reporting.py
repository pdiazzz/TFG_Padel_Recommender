from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import textwrap

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages

from . import config
from .io import load_matches_metadata, read_csv_if_exists, write_csv
from .recommender import RULE_DOCUMENTATION

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "pdf.compression": 0,
    }
)

INSUFFICIENT_RULE = "no_recommendation_due_to_insufficient_evidence"
STANDARD_LIMITATION_TEXT = (
    "Orientación heurística basada en métricas agregadas del partido. "
    "No incorpora vídeo, marcador contextual, estado físico ni instrucciones tácticas previas."
)
PLAYER_CARD_COLUMNS = [
    "match_id",
    "match_label",
    "player",
    "rules_triggered",
    "num_rules_triggered",
    "evidence_metrics",
    "evidence_values",
    "formatted_evidence",
    "player_profile",
    "priority_label",
    "priority_reason",
    "priority_score",
    "tactical_diagnosis",
    "main_recommendation",
    "secondary_recommendation",
    "coach_note",
    "limitations",
]
PLAYER_GLOBAL_COLUMNS = [
    "player",
    "matches_with_recommendations",
    "total_cards",
    "total_rules_triggered",
    "most_common_profile",
    "most_common_rules",
    "high_priority_cards",
    "global_tactical_reading",
    "global_recommendation",
    "caution",
]
MATCH_SUMMARY_COLUMNS = [
    "match_id",
    "match_label",
    "player_cards",
    "pair_recommendations",
    "high_priority_player_cards",
    "main_player_profiles",
    "players_with_high_priority",
    "summary_text",
]


PROFILE_DETAILS = {
    "Atacante de alto riesgo": {
        "diagnosis": (
            "Jugador con alta producción ofensiva, pero también con exposición elevada "
            "al error respecto al contexto del partido."
        ),
        "main": (
            "Limitar sus situaciones de ataque directo y buscar contextos que aumenten "
            "su toma de riesgo, evitando concederle bolas cómodas de finalización."
        ),
        "secondary": (
            "Forzarle a decidir desde posiciones menos ventajosas y revisar en vídeo "
            "si los errores aparecen bajo presión sostenida."
        ),
        "score_bonus": 1.0,
    },
    "Finalizador eficiente": {
        "diagnosis": (
            "Jugador con buena eficiencia ofensiva y sin exceso de error relativo "
            "dentro del partido."
        ),
        "main": (
            "Evitar concederle bolas cómodas de finalización y reducir situaciones "
            "en las que pueda atacar con ventaja."
        ),
        "secondary": (
            "Priorizar bolas bajas, profundas o incómodas antes de permitirle atacar "
            "desde zonas favorables."
        ),
        "score_bonus": 0.5,
    },
    "Constructor del punto": {
        "diagnosis": (
            "Jugador con alto volumen de intervención y menor producción directa de "
            "winners, interpretable como posible constructor o estabilizador del punto."
        ),
        "main": (
            "Interpretarlo como constructor del punto; conviene evitar precipitar la "
            "finalización contra él y usar su volumen de juego para desplazar a la pareja rival."
        ),
        "secondary": (
            "Variar direcciones y ritmos para que su volumen no estabilice el intercambio."
        ),
        "score_bonus": 0.5,
    },
    "Foco potencial de presión": {
        "diagnosis": (
            "Jugador con porcentaje de error superior a la media del partido, sin "
            "evidencia simultánea de alta producción ofensiva."
        ),
        "main": (
            "Aumentar la presión o el volumen de juego sobre este jugador, siempre "
            "con cautela contextual."
        ),
        "secondary": (
            "Buscar patrones sostenidos que eleven la exigencia sin asumir riesgos innecesarios."
        ),
        "score_bonus": 0.0,
    },
    "Atacante agresivo": {
        "diagnosis": (
            "Jugador con producción ofensiva elevada y tendencia a asumir riesgo, "
            "aunque sin quedar claramente penalizado por error relativo según las reglas disponibles."
        ),
        "main": (
            "Reducir sus opciones de ataque directo y obligarle a construir el punto "
            "desde posiciones menos favorables."
        ),
        "secondary": (
            "Evitar bolas cómodas de transición y comprobar si su agresividad varía con el marcador."
        ),
        "score_bonus": 0.0,
    },
    "Perfil mixto ofensivo-constructor": {
        "diagnosis": (
            "Jugador que combina eficiencia ofensiva relativa con alto volumen de intervención, "
            "por lo que puede alternar funciones de construcción y finalización dentro del partido."
        ),
        "main": (
            "Evitar concederle situaciones cómodas de finalización, pero sin ignorar su papel "
            "en la construcción del punto y en la estabilización del intercambio."
        ),
        "secondary": (
            "Observar si su volumen de intervención aparece en fases de control o en fases de cierre "
            "del punto antes de fijar una pauta táctica cerrada."
        ),
        "score_bonus": 0.75,
    },
    "Perfil mixto": {
        "diagnosis": (
            "Jugador con señales métricas mixtas; requiere interpretación contextual del entrenador."
        ),
        "main": (
            "Revisar conjuntamente las métricas activadas y contrastarlas con vídeo "
            "o criterio experto antes de aplicar una orientación táctica cerrada."
        ),
        "secondary": "Usar la ficha como hipótesis de trabajo, no como instrucción cerrada.",
        "score_bonus": 0.0,
    },
    "Sin evidencia suficiente": {
        "diagnosis": (
            "No se detecta evidencia cuantitativa suficiente para generar una orientación "
            "táctica individual robusta."
        ),
        "main": "No formular una orientación táctica específica sin información adicional.",
        "secondary": "Ampliar muestra, revisar vídeo o incorporar contexto de marcador antes de decidir.",
        "score_bonus": 0.0,
    },
}


GLOBAL_CAUTION = (
    "Lectura heurística sobre muestra limitada; no incorpora vídeo, estado físico, "
    "marcador contextual ni instrucciones del cuerpo técnico."
)


def load_recommendations(path: Path | None = None) -> pd.DataFrame:
    path = path or config.RECOMMENDATIONS_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}. Ejecuta primero: python scripts/generate_recommendations.py"
        )
    recommendations = read_csv_if_exists(path)
    validate_recommendation_columns(recommendations)
    if recommendations.empty:
        raise ValueError("recommendations.csv existe, pero está vacío.")
    return recommendations


def validate_recommendation_columns(recommendations: pd.DataFrame) -> None:
    missing = [column for column in config.RECOMMENDATION_COLUMNS if column not in recommendations.columns]
    if missing:
        raise ValueError(
            "recommendations.csv no conserva todas las columnas de trazabilidad. "
            f"Faltan: {', '.join(missing)}"
        )


def _clean_pair_label(value: object) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    return text.replace(" - ", "/").replace(" / ", "/")


def _year_from_match_id(match_id: str) -> str:
    match = re.search(r"(20\d{2})", match_id)
    return match.group(1) if match else ""


def _fallback_match_label(match_id: str) -> str:
    text = match_id.replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else match_id


def build_match_labels() -> dict[str, str]:
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


EVIDENCE_LABELS = {
    "error_pct": ["Error%"],
    "winner_pct": ["Winner%"],
    "winner_pct_and_error_pct": ["Winner%", "Error%"],
    "total_golpes_and_winner_pct": ["Golpes", "Winner%"],
    "efectividad_ofensiva": ["Efectividad ofensiva"],
    "pair_error_pct_vs_rival": ["Error% de pareja frente al rival"],
}

DISPLAY_TEXT_REPLACEMENTS = {
    "presion": "presión",
    "metricas": "métricas",
    "recomendacion": "orientación",
    "tactica": "táctica",
    "tactico": "táctico",
    "tacticas": "tácticas",
    "automaticamente": "automáticamente",
    "comodas": "cómodas",
    "finalizacion": "finalización",
    "produccion": "producción",
    "intervencion": "intervención",
    "hipotesis": "hipótesis",
    "fisico": "físico",
    "video": "vídeo",
    "accion": "acción",
    "autonoma": "autónoma",
    "orientacion": "orientación",
    "mas": "más",
    "segun": "según",
    "senales": "señales",
}


def _split_semicolon(value: object) -> list[str]:
    if pd.isna(value):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def _format_numeric_value(value: str, label: str) -> str:
    try:
        number = float(value.replace(",", "."))
    except ValueError:
        return value
    if label == "Golpes" and number.is_integer():
        return str(int(number))
    return f"{number:.2f}"


def format_evidence(evidence_metrics: object, evidence_values: object) -> str:
    metrics = _split_semicolon(evidence_metrics)
    values = _split_semicolon(evidence_values)
    labels: list[str] = []
    for metric in metrics:
        labels.extend(EVIDENCE_LABELS.get(metric, [metric.replace("_", " ")]))
    if not labels:
        labels = ["valor"] * len(values)
    if len(values) > len(labels):
        labels.extend(["valor"] * (len(values) - len(labels)))

    formatted: list[str] = []
    for index, value in enumerate(values):
        label = labels[index] if index < len(labels) else "valor"
        clean_value = _format_numeric_value(value, label)
        formatted.append(f"{label} = {clean_value}")
    return "; ".join(formatted)


def _normalize_display_text(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    for old, new in DISPLAY_TEXT_REPLACEMENTS.items():
        text = re.sub(rf"\b{old}\b", new, text)
    return text


def _display_recommendation(row: pd.Series) -> str:
    if str(row.get("rule_applied", "")) == "pair_error_pct_above_rival":
        return (
            "Priorizar patrones de intercambio que mantengan presión sostenida sobre la pareja rival "
            "y favorezcan la aparición de errores no forzados, evitando asumir riesgos innecesarios "
            "en fases neutras del punto."
        )
    return _normalize_display_text(row.get("recommendation", ""))


def _unique_join(values: pd.Series | list[object], sep: str = "; ") -> str:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if pd.isna(value):
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return sep.join(result)


def assign_player_profile(rules: set[str]) -> str:
    if not rules or rules == {INSUFFICIENT_RULE}:
        return "Sin evidencia suficiente"
    high_error = "player_error_pct_above_match_mean" in rules
    high_winner_error = "high_winner_high_error" in rules
    efficient = "high_offensive_efficiency_low_error" in rules
    high_volume = "high_volume_low_winner" in rules

    if high_winner_error and high_error:
        return "Atacante de alto riesgo"
    if efficient and high_volume:
        return "Perfil mixto ofensivo-constructor"
    if efficient and not high_error:
        return "Finalizador eficiente"
    if high_volume and not high_winner_error and not high_error:
        return "Constructor del punto"
    if high_error and not high_winner_error:
        return "Foco potencial de presión"
    if high_winner_error and not high_error:
        return "Atacante agresivo"
    if len(rules) > 1:
        return "Perfil mixto"
    return "Sin evidencia suficiente"


def priority_label(num_rules: int, rules: set[str], profile: str) -> str:
    if num_rules <= 0 or rules == {INSUFFICIENT_RULE}:
        return "Sin evidencia"
    if num_rules >= 2:
        return "Alta"
    if profile == "Atacante de alto riesgo":
        return "Alta"
    if "high_winner_high_error" in rules and "player_error_pct_above_match_mean" in rules:
        return "Alta"
    if rules == {"high_volume_low_winner"}:
        return "Baja"
    if profile in {"Finalizador eficiente", "Foco potencial de presión", "Atacante agresivo"}:
        return "Media"
    return "Media"


def priority_reason(num_rules: int, rules: set[str], profile: str) -> str:
    if num_rules <= 0 or rules == {INSUFFICIENT_RULE}:
        return "Sin evidencia suficiente para priorizar."
    if profile == "Atacante de alto riesgo":
        return "Alta por perfil de atacante de alto riesgo."
    if "high_winner_high_error" in rules and "player_error_pct_above_match_mean" in rules:
        return "Alta por combinación de evidencia ofensiva y error elevado."
    if num_rules >= 2:
        return "Alta por activación simultánea de varias reglas."
    if rules == {"high_volume_low_winner"}:
        return "Baja por perfil contextual de construcción con una única regla."
    return "Media por evidencia clara en una regla individual."


def priority_score(num_rules: int, profile: str) -> float:
    bonus = float(PROFILE_DETAILS.get(profile, {}).get("score_bonus", 0.0))
    return round(float(num_rules) + bonus, 2)


def _coach_note() -> str:
    return (
        "Esta lectura debe utilizarse como hipótesis de análisis táctico y contrastarse "
        "con vídeo, marcador, estado físico e instrucciones del cuerpo técnico."
    )


def build_player_recommendation_cards(recommendations: pd.DataFrame) -> pd.DataFrame:
    validate_recommendation_columns(recommendations)
    player_rows = recommendations[
        (recommendations["scope"] == "player") & (recommendations["rule_applied"] != INSUFFICIENT_RULE)
    ].copy()
    if player_rows.empty:
        return pd.DataFrame(columns=PLAYER_CARD_COLUMNS)

    match_labels = build_match_labels()
    cards: list[dict[str, object]] = []
    for (match_id, player), group in player_rows.groupby(["match_id", "target"], sort=True):
        rules = [str(rule) for rule in group["rule_applied"].dropna().tolist()]
        rule_set = set(rules)
        profile = assign_player_profile(rule_set)
        details = PROFILE_DETAILS[profile]
        num_rules = len(set(rules))
        label = priority_label(num_rules, rule_set, profile)
        reason = priority_reason(num_rules, rule_set, profile)
        raw_metrics = "; ".join(group["evidence_metric"].dropna().astype(str).tolist())
        raw_values = "; ".join(group["evidence_value"].dropna().astype(str).tolist())
        original_recommendations = [
            _normalize_display_text(rec)
            for rec in group["recommendation"].dropna().astype(str).tolist()
            if rec != "no_recommendation_due_to_insufficient_evidence"
        ]
        secondary = _unique_join(original_recommendations[:3])
        if not secondary or secondary == details["main"]:
            secondary = str(details["secondary"])

        cards.append(
            {
                "match_id": match_id,
                "match_label": match_labels.get(str(match_id), _fallback_match_label(str(match_id))),
                "player": player,
                "rules_triggered": _unique_join(rules),
                "num_rules_triggered": num_rules,
                "evidence_metrics": _unique_join(group["evidence_metric"]),
                "evidence_values": _unique_join(group["evidence_value"]),
                "formatted_evidence": format_evidence(raw_metrics, raw_values),
                "player_profile": profile,
                "priority_label": label,
                "priority_reason": reason,
                "priority_score": priority_score(num_rules, profile),
                "tactical_diagnosis": details["diagnosis"],
                "main_recommendation": details["main"],
                "secondary_recommendation": secondary,
                "coach_note": _coach_note(),
                "limitations": STANDARD_LIMITATION_TEXT,
            }
        )
    return pd.DataFrame(cards, columns=PLAYER_CARD_COLUMNS).sort_values(
        ["match_id", "priority_score", "player"], ascending=[True, False, True]
    )


def _most_common(values: list[str], top_n: int = 3) -> str:
    if not values:
        return ""
    counter = Counter(values)
    return "; ".join(f"{key} ({count})" for key, count in counter.most_common(top_n))


def _global_reading(profile: str) -> tuple[str, str]:
    if profile == "Atacante de alto riesgo":
        return (
            "El jugador aparece recurrentemente asociado a producción ofensiva elevada "
            "y exposición al error dentro de la muestra analizada.",
            "Preparar patrones que limiten sus finalizaciones cómodas y aumenten la exigencia de su toma de riesgo.",
        )
    if profile == "Finalizador eficiente":
        return (
            "El jugador aparece como finalizador eficiente en las situaciones detectadas, "
            "combinando producción ofensiva con control relativo del error.",
            "Reducir las bolas cómodas de ataque y obligarle a finalizar desde contextos menos favorables.",
        )
    if profile == "Constructor del punto":
        return (
            "El jugador aparece principalmente como perfil de alto volumen y menor finalización directa, "
            "compatible con un rol de construcción o estabilización del punto.",
            "Usar variaciones de ritmo y dirección para impedir que estabilice el intercambio.",
        )
    if profile == "Foco potencial de presión":
        return (
            "El jugador presenta señales recurrentes de error relativo elevado, por lo que puede ser "
            "objeto de presión táctica contextual.",
            "Aumentar progresivamente el volumen de juego sobre él, evitando asumir riesgos no justificados.",
        )
    if profile == "Perfil mixto ofensivo-constructor":
        return (
            "El jugador combina señales de eficiencia ofensiva con alto volumen de intervención, "
            "lo que sugiere una alternancia entre construcción y finalización.",
            "Evitar sus situaciones cómodas de finalización sin perder de vista su papel en la construcción del punto.",
        )
    return (
        "El jugador presenta señales heterogéneas entre partidos, por lo que la interpretación debe "
        "apoyarse en contexto táctico adicional.",
        "Contrastar las fichas con vídeo y criterio experto antes de fijar una orientación global.",
    )


def build_player_global_recommendation_summary(cards: pd.DataFrame) -> pd.DataFrame:
    if cards.empty:
        return pd.DataFrame(columns=PLAYER_GLOBAL_COLUMNS)
    rows: list[dict[str, object]] = []
    for player, group in cards.groupby("player", sort=True):
        profiles = group["player_profile"].dropna().astype(str).tolist()
        rules = []
        for value in group["rules_triggered"].dropna().astype(str):
            rules.extend([rule.strip() for rule in value.split(";") if rule.strip()])
        most_common_profile = Counter(profiles).most_common(1)[0][0] if profiles else "Sin evidencia suficiente"
        reading, recommendation = _global_reading(most_common_profile)
        rows.append(
            {
                "player": player,
                "matches_with_recommendations": group["match_id"].nunique(),
                "total_cards": len(group),
                "total_rules_triggered": int(group["num_rules_triggered"].sum()),
                "most_common_profile": most_common_profile,
                "most_common_rules": _most_common(rules),
                "high_priority_cards": int((group["priority_label"] == "Alta").sum()),
                "global_tactical_reading": reading,
                "global_recommendation": recommendation,
                "caution": GLOBAL_CAUTION,
            }
        )
    return pd.DataFrame(rows, columns=PLAYER_GLOBAL_COLUMNS).sort_values(
        ["high_priority_cards", "total_rules_triggered", "player"], ascending=[False, False, True]
    )


def build_match_recommendation_summary(recommendations: pd.DataFrame, cards: pd.DataFrame) -> pd.DataFrame:
    validate_recommendation_columns(recommendations)
    match_ids = sorted(set(recommendations["match_id"].dropna().astype(str)) | set(cards.get("match_id", [])))
    match_labels = build_match_labels()
    rows: list[dict[str, object]] = []
    for match_id in match_ids:
        match_cards = cards[cards["match_id"] == match_id] if not cards.empty else pd.DataFrame(columns=PLAYER_CARD_COLUMNS)
        pair_recs = recommendations[(recommendations["match_id"] == match_id) & (recommendations["scope"] == "pair")]
        high_cards = match_cards[match_cards["priority_label"] == "Alta"]
        profiles = _most_common(match_cards["player_profile"].dropna().astype(str).tolist())
        high_players = _unique_join(high_cards["player"]) if not high_cards.empty else ""
        if match_cards.empty:
            summary_text = (
                "No se generan fichas individuales de jugador con las reglas disponibles; "
                "la lectura debe apoyarse en evidencia adicional."
            )
        else:
            main_profile = match_cards["player_profile"].mode().iloc[0]
            summary_text = (
                f"Predominan perfiles de tipo {main_profile.lower()} en las fichas de jugador. "
                f"El partido contiene {len(high_cards)} ficha(s) de prioridad alta y {len(pair_recs)} orientación(es) de pareja."
            )
        rows.append(
            {
                "match_id": match_id,
                "match_label": match_labels.get(str(match_id), _fallback_match_label(str(match_id))),
                "player_cards": len(match_cards),
                "pair_recommendations": len(pair_recs),
                "high_priority_player_cards": len(high_cards),
                "main_player_profiles": profiles,
                "players_with_high_priority": high_players,
                "summary_text": summary_text,
            }
        )
    return pd.DataFrame(rows, columns=MATCH_SUMMARY_COLUMNS)


def build_recommendations_summary(
    recommendations: pd.DataFrame,
    cards: pd.DataFrame | None = None,
) -> pd.DataFrame:
    validate_recommendation_columns(recommendations)
    cards = build_player_recommendation_cards(recommendations) if cards is None else cards
    total = len(recommendations)
    insufficient = int((recommendations["rule_applied"] == INSUFFICIENT_RULE).sum())
    real = total - insufficient
    pair_recs = int((recommendations["scope"] == "pair").sum())
    player_cards = len(cards)
    players_with_cards = int(cards["player"].nunique()) if not cards.empty else 0
    distinct_rules = int(recommendations.loc[recommendations["rule_applied"] != INSUFFICIENT_RULE, "rule_applied"].nunique())
    matches = int(recommendations["match_id"].nunique())

    rows: list[dict[str, object]] = [
        ("total", "all", total, "Todas las filas de recommendations.csv."),
        ("total", "real_recommendations", real, "Filas con orientación táctica trazable."),
        ("total", "insufficient_evidence", insufficient, "Filas sin evidencia suficiente."),
        ("total", "player_recommendation_cards", player_cards, "Fichas consolidadas jugador-partido."),
        ("total", "pair_recommendations", pair_recs, "Orientaciones con scope pair."),
        ("total", "players_with_cards", players_with_cards, "Jugadores con al menos una ficha."),
        ("total", "distinct_rules", distinct_rules, "Reglas distintas activadas."),
        ("total", "matches_with_recommendations", matches, "Partidos con orientaciones."),
    ]
    output = [
        {
            "summary_type": section,
            "category": category,
            "count": int(count),
            "share_pct": round(int(count) / total * 100, 2) if total else 0.0,
            "notes": notes,
        }
        for section, category, count, notes in rows
    ]

    for section, column in [("by_match", "match_id"), ("by_rule", "rule_applied"), ("by_scope", "scope")]:
        counts = recommendations.groupby(column, dropna=False).size().sort_values(ascending=False)
        for category, count in counts.items():
            output.append(
                {
                    "summary_type": section,
                    "category": category,
                    "count": int(count),
                    "share_pct": round(int(count) / total * 100, 2) if total else 0.0,
                    "notes": "",
                }
            )
    return pd.DataFrame(output, columns=["summary_type", "category", "count", "share_pct", "notes"])


def _latex_escape(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _write_tabularx(path: Path, headers: list[str], rows: list[list[object]], spec: str) -> None:
    lines = [
        r"\begin{tabularx}{\textwidth}{" + spec + "}",
        r"\toprule",
        " & ".join(_latex_escape(header) for header in headers) + r" \\",
        r"\midrule",
    ]
    for row in rows:
        lines.append(" & ".join(_latex_escape(value) for value in row) + r" \\")
    lines.extend([r"\bottomrule", r"\end{tabularx}", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _select_profile_examples(cards: pd.DataFrame, max_per_group: int = 1) -> pd.DataFrame:
    group_column = next(
        (column for column in ["player_profile", "rules_triggered", "main_recommendation"] if column in cards.columns),
        None,
    )
    if cards.empty or group_column is None:
        return cards.head(0)

    profile_order = {profile: idx for idx, profile in enumerate(PROFILE_DETAILS)}
    data = cards.copy()
    if "player_profile" not in data.columns:
        data["player_profile"] = ""
    data["_profile_order"] = data["player_profile"].map(profile_order).fillna(len(profile_order)).astype(int)
    if "priority_score" not in data.columns:
        data["priority_score"] = 0
    data["priority_score"] = pd.to_numeric(data["priority_score"], errors="coerce").fillna(0)
    scored_columns = ["formatted_evidence", "tactical_diagnosis", "main_recommendation"]
    for column in scored_columns:
        if column not in data.columns:
            data[column] = ""
        data[column] = data[column].fillna("").astype(str)
    data["_missing_fields"] = data[scored_columns].apply(lambda row: sum(not value.strip() for value in row), axis=1)
    data["_evidence_items"] = data["formatted_evidence"].str.count("=")
    data["_text_length"] = (
        data["formatted_evidence"].str.len()
        + data["main_recommendation"].str.len()
        + data["tactical_diagnosis"].str.len() * 0.35
    )

    selected = []
    data = data.sort_values(
        ["_profile_order", "_missing_fields", "_evidence_items", "priority_score", "_text_length", "match_id", "player"],
        ascending=[True, True, False, False, True, True, True],
    )
    for _, group in data.groupby(group_column, sort=False):
        selected.append(group.head(max_per_group))
    if not selected:
        return cards.head(0)
    helper_columns = ["_profile_order", "_missing_fields", "_evidence_items", "_text_length"]
    return pd.concat(selected, ignore_index=True).drop(columns=helper_columns)


def write_recommendation_latex_tables(
    recommendations: pd.DataFrame,
    summary: pd.DataFrame,
    cards: pd.DataFrame,
    global_summary: pd.DataFrame,
) -> None:
    compact_rows = [
        ["Orientaciones con evidencia", summary.loc[summary["category"] == "real_recommendations", "count"].iloc[0]],
        ["Fichas jugador-partido", len(cards)],
        ["Orientaciones de pareja", int((recommendations["scope"] == "pair").sum())],
        ["Jugadores con ficha", cards["player"].nunique() if not cards.empty else 0],
        ["Reglas distintas", recommendations.loc[recommendations["rule_applied"] != INSUFFICIENT_RULE, "rule_applied"].nunique()],
        ["Partidos con orientaciones", recommendations["match_id"].nunique()],
        ["Filas sin evidencia suficiente", int((recommendations["rule_applied"] == INSUFFICIENT_RULE).sum())],
    ]
    _write_tabularx(config.RECOMMENDATIONS_SUMMARY_TEX_PATH, ["Indicador", "Valor"], compact_rows, "Xr")

    examples = _select_profile_examples(cards, max_per_group=1)
    example_rows = [
        [
            row["match_label"],
            row["player"],
            row["player_profile"],
            row["priority_label"],
            row["formatted_evidence"],
            row["main_recommendation"],
        ]
        for _, row in examples.iterrows()
    ]
    example_headers = ["Partido", "Jugador", "Perfil", "Prioridad", "Evidencia", "Orientación principal"]
    example_spec = "p{0.20\\textwidth}p{0.13\\textwidth}p{0.15\\textwidth}p{0.09\\textwidth}p{0.18\\textwidth}X"
    for path in [
        config.PLAYER_RECOMMENDATION_EXAMPLES_TEX_PATH,
        config.MEMORY_PLAYER_RECOMMENDATION_EXAMPLES_TEX_PATH,
    ]:
        _write_tabularx(path, example_headers, example_rows, example_spec)

    global_rows = [
        [
            row["player"],
            row["most_common_profile"],
            row["total_cards"],
            row["high_priority_cards"],
            row["global_recommendation"],
        ]
        for _, row in global_summary.iterrows()
    ]
    _write_tabularx(
        config.GLOBAL_PLAYER_SUMMARY_TEX_PATH,
        ["Jugador", "Perfil más frecuente", "Fichas", "Prioridad alta", "Orientación global"],
        global_rows,
        "p{0.16\\textwidth}p{0.20\\textwidth}r r X",
    )


def write_recommendation_tables(recommendations: pd.DataFrame) -> dict[str, pd.DataFrame]:
    config.ensure_directories()
    validate_recommendation_columns(recommendations)
    if recommendations.empty:
        raise ValueError("No se pueden generar tablas de orientaciones: recommendations.csv está vacío.")

    cards = build_player_recommendation_cards(recommendations)
    global_summary = build_player_global_recommendation_summary(cards)
    match_summary = build_match_recommendation_summary(recommendations, cards)
    summary = build_recommendations_summary(recommendations, cards)

    write_csv(summary, config.RECOMMENDATIONS_SUMMARY_PATH)
    write_csv(cards, config.PLAYER_RECOMMENDATION_CARDS_PATH)
    write_csv(global_summary, config.PLAYER_GLOBAL_RECOMMENDATION_SUMMARY_PATH)
    write_csv(match_summary, config.MATCH_RECOMMENDATION_SUMMARY_PATH)
    write_recommendation_latex_tables(recommendations, summary, cards, global_summary)
    return {
        "summary": summary,
        "cards": cards,
        "global_summary": global_summary,
        "match_summary": match_summary,
    }


def generate_recommendations_summary_from_csv() -> pd.DataFrame:
    recommendations = load_recommendations()
    return write_recommendation_tables(recommendations)["summary"]


def write_recommendations_summary(recommendations: pd.DataFrame) -> pd.DataFrame:
    return write_recommendation_tables(recommendations)["summary"]


def _wrap(value: object, width: int) -> list[str]:
    text = "" if pd.isna(value) else str(value)
    return textwrap.wrap(text, width=width, break_long_words=False, replace_whitespace=False) or [""]


@dataclass
class PdfWriter:
    pdf: PdfPages
    page_number: int = 1
    title: str = ""
    fig: plt.Figure | None = None
    y: float = 0.93

    def start_page(self, title: str) -> None:
        self.finish_page()
        self.title = title
        self.fig = plt.figure(figsize=(8.27, 11.69))
        self.fig.patch.set_facecolor("white")
        self.y = 0.93
        self.fig.text(0.07, self.y, title, fontsize=15, weight="bold", va="top")
        self.y -= 0.045

    def finish_page(self) -> None:
        if self.fig is None:
            return
        self.fig.text(0.5, 0.025, f"Página {self.page_number}", ha="center", fontsize=8, color="#555555")
        self.pdf.savefig(self.fig)
        plt.close(self.fig)
        self.page_number += 1
        self.fig = None

    def ensure(self, lines: int = 1, line_height: float = 0.018) -> None:
        if self.fig is None:
            self.start_page(self.title or "Informe")
        if self.y - lines * line_height < 0.065:
            self.start_page(f"{self.title} (cont.)")

    def text(self, value: object, size: float = 9.2, weight: str = "normal", width: int = 95, indent: float = 0.0) -> None:
        for line in _wrap(value, width):
            self.ensure(1, 0.018 * size / 9.2)
            assert self.fig is not None
            self.fig.text(0.07 + indent, self.y, line, fontsize=size, weight=weight, va="top")
            self.y -= 0.018 * size / 9.2
        self.y -= 0.006

    def heading(self, value: object, size: float = 11.5) -> None:
        self.ensure(2)
        self.text(value, size=size, weight="bold", width=88)

    def field(self, label: str, value: object, width: int = 92) -> None:
        self.text(f"{label}: {value}", size=8.6, width=width, indent=0.015)

    def spacer(self, amount: float = 0.012) -> None:
        self.y -= amount


def _summary_value(summary: pd.DataFrame, category: str) -> int:
    values = summary.loc[summary["category"] == category, "count"]
    return int(values.iloc[0]) if len(values) else 0


def _add_executive_summary(
    writer: PdfWriter,
    recommendations: pd.DataFrame,
    summary: pd.DataFrame,
    cards: pd.DataFrame,
    generated_at: datetime,
) -> None:
    writer.start_page("Resumen ejecutivo")
    writer.text("Informe de orientaciones tácticas", size=17, weight="bold")
    writer.text(f"Fecha de generación: {generated_at:%Y-%m-%d %H:%M}", size=9.5)
    writer.field("Total de filas en recommendations.csv", len(recommendations))
    writer.field("Orientaciones con evidencia", _summary_value(summary, "real_recommendations"))
    writer.field("Filas sin evidencia suficiente", _summary_value(summary, "insufficient_evidence"))
    writer.field("Fichas jugador-partido", len(cards))
    writer.field("Jugadores con ficha", cards["player"].nunique() if not cards.empty else 0)
    writer.field("Orientaciones de pareja", int((recommendations["scope"] == "pair").sum()))
    writer.spacer()
    match_labels = build_match_labels()
    for section, title in [("by_match", "Distribución por partido"), ("by_rule", "Distribución por regla"), ("by_scope", "Distribución por scope")]:
        writer.heading(title)
        subset = summary[summary["summary_type"] == section]
        for _, row in subset.iterrows():
            category = match_labels.get(str(row["category"]), row["category"]) if section == "by_match" else row["category"]
            writer.text(f"- {category}: {row['count']} ({row['share_pct']}%)", size=8.4, width=90)
    writer.heading("Aviso metodológico")
    writer.text(
        "Las salidas son orientaciones tácticas heurísticas e interpretables basadas en métricas agregadas. "
        "El sistema no predice automáticamente la mejor acción táctica, no se presenta como predicción autónoma "
        "y debe entenderse como orientación revisable por el entrenador.",
        size=9,
    )


def _add_criteria_page(writer: PdfWriter) -> None:
    writer.start_page("Criterio de generación")
    writer.text(
        "Las orientaciones se generan mediante reglas heurísticas sobre métricas agregadas por jugador-partido "
        "y pareja-partido. La consolidación agrupa varias reglas activadas para un mismo jugador dentro del mismo "
        "partido y las resume en una ficha táctica. El sistema no predice automáticamente la mejor acción, no "
        "funciona como decisión autónoma y no sustituye al entrenador.",
        size=9.2,
    )
    writer.heading("Reglas por fila")
    for rule in RULE_DOCUMENTATION:
        writer.text(rule["rule_applied"], size=9.2, weight="bold")
        writer.field("Condición", rule["condition"], width=90)
        writer.field("Salida", rule["recommendation_type"], width=90)
    writer.heading("Perfiles y prioridad")
    writer.text(
        "Los perfiles se asignan con prioridad fija: Atacante de alto riesgo, Finalizador eficiente, "
        "Constructor del punto, Foco potencial de presión, Atacante agresivo, Perfil mixto ofensivo-constructor, "
        "Perfil mixto y Sin evidencia suficiente.",
        size=9,
    )
    writer.text(
        "La prioridad es Alta cuando hay dos o más reglas activadas o un perfil de alto riesgo, Media con una "
        "regla de evidencia clara, Baja con una regla contextual de construcción y Sin evidencia si no hay "
        "reglas suficientes. El priority_score usa el número de reglas y pequeños bonos para perfiles "
        "especialmente informativos.",
        size=9,
    )


def _add_match_cards_pages(
    writer: PdfWriter,
    cards: pd.DataFrame,
    match_summary: pd.DataFrame,
    recommendations: pd.DataFrame,
) -> None:
    if cards.empty:
        writer.start_page("Fichas por partido")
        writer.text("No hay orientaciones individuales de tipo player para consolidar.", size=10)
        return
    for match_id, group in cards.groupby("match_id", sort=True):
        match_label = str(group["match_label"].iloc[0]) if "match_label" in group.columns else _fallback_match_label(str(match_id))
        writer.start_page(f"Partido: {match_label}")
        writer.field("match_id técnico", match_id)
        summary = match_summary[match_summary["match_id"] == match_id]
        if not summary.empty:
            row = summary.iloc[0]
            writer.field("Fichas de jugador", row["player_cards"])
            writer.field("Fichas de prioridad alta", row["high_priority_player_cards"])
            writer.field("Orientaciones de pareja", row["pair_recommendations"])
            writer.field("Perfiles principales", row["main_player_profiles"])
            writer.text(row["summary_text"], size=9)
        pair_rows = recommendations[(recommendations["match_id"] == match_id) & (recommendations["scope"] == "pair")]
        if not pair_rows.empty:
            writer.heading("Orientaciones de pareja")
            for _, pair in pair_rows.iterrows():
                evidence = format_evidence(pair["evidence_metric"], pair["evidence_value"])
                writer.text(f"- {pair['target']}: {_display_recommendation(pair)} Evidencia: {evidence}.", size=8.4, width=92)
        for _, card in group.sort_values(["priority_score", "player"], ascending=[False, True]).iterrows():
            writer.ensure(9)
            writer.heading(f"Ficha: {card['player']}")
            writer.field("Perfil táctico", card["player_profile"])
            writer.field("Prioridad", f"{card['priority_label']} (score {card['priority_score']})")
            writer.field("Motivo de prioridad", card["priority_reason"])
            writer.field("Reglas activadas", card["rules_triggered"])
            writer.field("Evidencias", card["formatted_evidence"])
            writer.field("Diagnóstico táctico", card["tactical_diagnosis"])
            writer.field("Orientación principal", card["main_recommendation"])
            writer.field("Orientación secundaria", card["secondary_recommendation"])
            writer.field("Nota para el entrenador", card["coach_note"])
            writer.field("Limitaciones", card["limitations"])
            writer.spacer(0.012)


def _add_profiles_explanation(writer: PdfWriter) -> None:
    writer.start_page("Perfiles y prioridad")
    for profile, details in PROFILE_DETAILS.items():
        writer.text(profile, size=10, weight="bold")
        writer.field("Diagnóstico", details["diagnosis"], width=90)
        writer.field("Orientación principal", details["main"], width=90)
    writer.heading("Prioridad")
    writer.text(
        "Alta: dos o más reglas activadas, perfil de alto riesgo o combinación de evidencia ofensiva y error "
        "elevado. Media: una regla con evidencia clara. Baja: constructor del punto con una única regla "
        "contextual. Sin evidencia: no hay reglas suficientes.",
        size=9,
    )


def _add_global_summary_pages(writer: PdfWriter, global_summary: pd.DataFrame) -> None:
    writer.start_page("Resumen global por jugador")
    if global_summary.empty:
        writer.text("No hay fichas globales de jugador.", size=10)
        return
    for _, row in global_summary.iterrows():
        writer.ensure(7)
        writer.heading(str(row["player"]))
        writer.field("Perfil más frecuente", row["most_common_profile"])
        writer.field("Fichas", row["total_cards"])
        writer.field("Reglas activadas", row["total_rules_triggered"])
        writer.field("Prioridad alta", row["high_priority_cards"])
        writer.field("Reglas frecuentes", row["most_common_rules"])
        writer.field("Lectura global", row["global_tactical_reading"])
        writer.field("Orientación global", row["global_recommendation"])
        writer.field("Cautela", row["caution"])
        writer.spacer(0.012)


def _write_pdf_with_fallback(
    target_path: Path,
    writer_func,
    *args: object,
) -> tuple[Path, str | None]:
    """Write a PDF atomically and keep a fallback when Windows locks the target."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.with_name(f".{target_path.stem}.tmp.pdf")
    fallback_path = target_path.with_name(f"{target_path.stem}_new.pdf")

    for path in (tmp_path, fallback_path):
        if path.exists():
            try:
                path.unlink()
            except PermissionError:
                pass

    writer_func(tmp_path, *args)
    try:
        tmp_path.replace(target_path)
        return target_path, None
    except PermissionError:
        tmp_path.replace(fallback_path)
        warning = (
            f"No se pudo sobrescribir {target_path} porque parece estar abierto. "
            f"Se ha generado una versión alternativa en {fallback_path}."
        )
        return fallback_path, warning


def _write_main_report(
    path: Path,
    recommendations: pd.DataFrame,
    summary: pd.DataFrame,
    cards: pd.DataFrame,
    match_summary: pd.DataFrame,
    generated_at: datetime,
) -> None:
    with PdfPages(path) as pdf:
        writer = PdfWriter(pdf)
        _add_executive_summary(writer, recommendations, summary, cards, generated_at)
        _add_criteria_page(writer)
        _add_match_cards_pages(writer, cards, match_summary, recommendations)
        writer.finish_page()


def _write_cards_report(
    path: Path,
    recommendations: pd.DataFrame,
    cards: pd.DataFrame,
    global_summary: pd.DataFrame,
    match_summary: pd.DataFrame,
    generated_at: datetime,
) -> None:
    with PdfPages(path) as pdf:
        writer = PdfWriter(pdf)
        writer.start_page("Fichas tácticas por jugador")
        writer.text("Informe específico de fichas consolidadas por jugador y partido.", size=13, weight="bold")
        writer.text(f"Fecha de generación: {generated_at:%Y-%m-%d %H:%M}", size=9)
        writer.field("Fichas jugador-partido", len(cards))
        writer.field("Jugadores con ficha", cards["player"].nunique() if not cards.empty else 0)
        writer.field("Partidos con fichas", cards["match_id"].nunique() if not cards.empty else 0)
        writer.text(
            "Las fichas consolidan reglas activadas en orientaciones tácticas heurísticas e interpretables "
            "basadas en métricas. No predicen la mejor acción, no son una decisión autónoma y funcionan como "
            "orientación revisable por el entrenador.",
            size=9,
        )
        _add_profiles_explanation(writer)
        _add_match_cards_pages(writer, cards, match_summary, recommendations)
        _add_global_summary_pages(writer, global_summary)
        writer.finish_page()


def generate_recommendations_report() -> dict[str, object]:
    config.ensure_directories()
    recommendations = load_recommendations()
    artifacts = write_recommendation_tables(recommendations)
    summary = artifacts["summary"]
    cards = artifacts["cards"]
    global_summary = artifacts["global_summary"]
    match_summary = artifacts["match_summary"]
    generated_at = datetime.now()

    recommendations_report, main_warning = _write_pdf_with_fallback(
        config.RECOMMENDATIONS_REPORT_PATH,
        _write_main_report,
        recommendations,
        summary,
        cards,
        match_summary,
        generated_at,
    )
    cards_report, cards_warning = _write_pdf_with_fallback(
        config.PLAYER_RECOMMENDATION_CARDS_REPORT_PATH,
        _write_cards_report,
        recommendations,
        cards,
        global_summary,
        match_summary,
        generated_at,
    )
    pdf_warnings = [warning for warning in (main_warning, cards_warning) if warning]

    return {
        "recommendations": recommendations,
        "summary": summary,
        "cards": cards,
        "global_summary": global_summary,
        "match_summary": match_summary,
        "recommendations_report": recommendations_report,
        "cards_report": cards_report,
        "pdf_warnings": pdf_warnings,
    }
