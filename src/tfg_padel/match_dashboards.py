from __future__ import annotations

from pathlib import Path
from textwrap import fill
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import gridspec
from matplotlib.patches import Circle, FancyBboxPatch, Wedge


DEFAULT_STYLE: dict[str, Any] = {
    "background": "#F5F7FA",
    "panel": "#FFFFFF",
    "text": "#1F2937",
    "muted": "#6B7280",
    "grid": "#E5E7EB",
    "pair_colors": ["#8C2F39", "#2D6A4F", "#A65E67", "#528B71"],
    "pair_soft_colors": ["#E7C9CD", "#D8EFE3", "#EFE0E2", "#E5F4EC"],
    "winner": "#3A86FF",
    "error": "#E76F51",
    "pressure": "#B08900",
    "neutral": "#9CA3AF",
    "soft_panel": "#F9FAFB",
}

PRIORITY_ORDER = {"Alta": 3, "Media": 2, "Baja": 1, "Sin evidencia": 0}


def _apply_dashboard_theme(style: dict[str, Any]) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.titleweight": "bold",
            "axes.labelcolor": style["text"],
            "xtick.color": style["muted"],
            "ytick.color": style["muted"],
            "figure.facecolor": style["background"],
            "savefig.facecolor": style["background"],
        }
    )


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def load_dashboard_inputs(project_root: Path) -> dict[str, pd.DataFrame]:
    """Load every table needed by the match dashboard generator."""
    project_root = Path(project_root).resolve()
    return {
        "project_root": project_root,
        "metadata": _read_csv(project_root / "data" / "metadata" / "matches_metadata.csv"),
        "matches_clean": _read_csv(project_root / "data" / "processed" / "matches_clean.csv"),
        "actions_clean": _read_csv(project_root / "data" / "processed" / "actions_clean.csv"),
        "player_match_metrics": _read_csv(project_root / "data" / "processed" / "player_match_metrics.csv"),
        "pair_match_metrics": _read_csv(project_root / "data" / "processed" / "pair_match_metrics.csv"),
        "recommendations": _read_csv(project_root / "outputs" / "tables" / "recommendations.csv"),
        "player_recommendation_cards": _read_csv(
            project_root / "outputs" / "tables" / "player_recommendation_cards.csv"
        ),
        "match_recommendation_summary": _read_csv(
            project_root / "outputs" / "tables" / "match_recommendation_summary.csv"
        ),
        "player_match_clusters": _read_csv(project_root / "outputs" / "tables" / "player_match_clusters.csv"),
        "cluster_profiles": _read_csv(project_root / "outputs" / "tables" / "cluster_profiles.csv"),
    }


def generate_all_match_dashboards(
    project_root: Path | str = ".",
    output_dir: Path | str | None = None,
) -> pd.DataFrame:
    """Generate one PNG dashboard for every match found in metadata/metrics."""
    project_root = Path(project_root).resolve()
    data = load_dashboard_inputs(project_root)
    output_dir = Path(output_dir) if output_dir is not None else project_root / "outputs" / "figures" / "match_dashboards"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = project_root / "outputs" / "tables" / "match_dashboard_summary.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    match_ids = _match_ids_from_data(data)
    rows: list[dict[str, object]] = []
    for match_id in match_ids:
        out_path = output_dir / f"dashboard_{match_id}.png"
        players = _match_filter(data["player_match_metrics"], match_id)
        pairs = _match_filter(data["pair_match_metrics"], match_id)
        recommendations = _match_filter(data["recommendations"], match_id)
        try:
            generated = generate_match_dashboard(match_id, data, out_path)
            status = "ok"
            notes = ""
        except Exception as exc:  # un partido con error no debe bloquear el resto del lote
            generated = out_path
            status = "error"
            notes = f"{type(exc).__name__}: {exc}"
        rows.append(
            {
                "match_id": match_id,
                "output_path": str(generated.relative_to(project_root)) if generated.exists() else str(generated),
                "players_count": int(players["jugador"].nunique()) if "jugador" in players.columns else len(players),
                "pairs_count": int(pairs["pareja"].nunique()) if "pareja" in pairs.columns else len(pairs),
                "recommendations_count": len(recommendations),
                "status": status,
                "notes": notes,
            }
        )

    summary = pd.DataFrame(
        rows,
        columns=[
            "match_id",
            "output_path",
            "players_count",
            "pairs_count",
            "recommendations_count",
            "status",
            "notes",
        ],
    )
    summary.to_csv(summary_path, index=False, lineterminator="\n")
    return summary


def generate_match_dashboard(
    match_id: str,
    data: dict[str, pd.DataFrame],
    output_path: Path | str,
    style: dict[str, Any] | None = None,
) -> Path:
    """Generate a single 16:9 dashboard for a match."""
    style = {**DEFAULT_STYLE, **(style or {})}
    _apply_dashboard_theme(style)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = data.get("metadata", pd.DataFrame())
    match_meta = _first_row(_match_filter(metadata, match_id))
    pair_metrics = _match_filter(data.get("pair_match_metrics", pd.DataFrame()), match_id)
    player_metrics = _player_rows_for_match(data, match_id)
    actions = _match_filter(data.get("actions_clean", pd.DataFrame()), match_id)
    recommendations = _match_filter(data.get("recommendations", pd.DataFrame()), match_id)
    cards = _match_filter(data.get("player_recommendation_cards", pd.DataFrame()), match_id)
    cluster_profiles = data.get("cluster_profiles", pd.DataFrame())
    cluster_info = _cluster_profile_map(cluster_profiles)
    pair_colors = _pair_color_map(match_meta, pair_metrics, style)
    pair_order = list(pair_colors.keys())
    pair_metrics = _sort_pair_metrics_by_pair(pair_metrics, pair_order)
    player_metrics = _sort_players_by_pair(player_metrics, match_meta, pair_metrics)

    fig = plt.figure(figsize=(18, 10), dpi=180, facecolor=style["background"])
    gs = gridspec.GridSpec(
        3,
        4,
        figure=fig,
        height_ratios=[0.92, 2.08, 2.42],
        hspace=0.16,
        wspace=0.11,
    )

    ax_header = fig.add_subplot(gs[0, 0:2])
    ax_actions = fig.add_subplot(gs[0, 2])
    ax_recommendations = fig.add_subplot(gs[0, 3])
    player_axes = [fig.add_subplot(gs[1, i]) for i in range(4)]
    ax_pairs = fig.add_subplot(gs[2, 0:2])
    ax_evolution = fig.add_subplot(gs[2, 2:4])

    _draw_header(ax_header, match_id, match_meta, pair_metrics, player_metrics, recommendations)
    _draw_action_summary(ax_actions, actions, player_metrics, cluster_info, pair_colors, style)
    _draw_recommendations(ax_recommendations, recommendations, cards)

    top_players = _select_player_cards(player_metrics)
    for idx, ax in enumerate(player_axes):
        if idx < len(top_players):
            row = top_players.iloc[idx]
            pair = str(_safe_get(row, "pareja", ""))
            _draw_player_card(ax, row, pair_colors.get(pair, style["neutral"]), cluster_info)
        else:
            _draw_empty_player_card(ax, style)

    if len(player_metrics) > 4:
        fig.text(
            0.5,
            0.51,
            "Nota: se muestran los 4 jugadores con mas golpes del partido.",
            ha="center",
            fontsize=8,
            color=style["muted"],
        )

    _draw_pair_comparison(ax_pairs, pair_metrics)
    _draw_evolution_or_scatter(ax_evolution, actions, player_metrics, match_id)

    fig.text(
        0.026,
        0.982,
        "Dashboard analítico por partido",
        ha="left",
        va="top",
        fontsize=12.5,
        weight="bold",
        color=style["text"],
    )
    fig.text(
        0.984,
        0.018,
        "Visualización basada en métricas agregadas. Las orientaciones son heurísticas y revisables.",
        ha="right",
        va="bottom",
        fontsize=7.2,
        color=style["muted"],
    )
    fig.subplots_adjust(left=0.025, right=0.985, top=0.955, bottom=0.078)
    fig.savefig(output_path, dpi=180, bbox_inches="tight", facecolor=style["background"])
    plt.close(fig)
    return output_path


def _draw_header(
    ax: plt.Axes,
    match_id: str,
    match_meta: pd.Series | None,
    pair_metrics: pd.DataFrame,
    player_metrics: pd.DataFrame,
    recommendations: pd.DataFrame,
) -> None:
    style = DEFAULT_STYLE
    _panel(ax, "Resumen del partido", style)
    tournament = _safe_get(match_meta, "tournament", "N/D")
    round_name = _safe_get(match_meta, "round", "N/D")
    pair_1 = _safe_get(match_meta, "pair_1", "Pareja A")
    pair_2 = _safe_get(match_meta, "pair_2", "Pareja B")
    title = f"{tournament} - {round_name}"
    subtitle = f"{pair_1} vs {pair_2}"
    total_golpes = _sum_col(pair_metrics, "total_golpes", player_metrics)
    total_winners = _sum_col(pair_metrics, "winners", player_metrics)
    total_errors = _sum_col(pair_metrics, "errores_totales", player_metrics)

    ax.text(0.04, 0.80, _shorten(title, 54), fontsize=12.5, weight="bold", color=style["text"], transform=ax.transAxes)
    ax.text(0.04, 0.67, _shorten(subtitle, 74), fontsize=9.2, color=style["muted"], transform=ax.transAxes)
    ax.text(0.04, 0.55, _shorten(match_id, 78), fontsize=7.5, color=style["muted"], transform=ax.transAxes)
    ax.text(
        0.04,
        0.39,
        f"Acciones: {_fmt_int(total_golpes)}   Winners: {_fmt_int(total_winners)}   Errores: {_fmt_int(total_errors)}   Orient.: {_fmt_int(len(recommendations))}",
        fontsize=9,
        weight="bold",
        color=style["text"],
        transform=ax.transAxes,
    )
    ax.text(
        0.04,
        0.27,
        "Marcador por sets: no disponible",
        fontsize=7.5,
        color=style["muted"],
        transform=ax.transAxes,
    )

    rows = _ensure_numeric(pair_metrics, ["total_golpes", "winners", "errores_totales", "winner_pct", "error_pct"])
    rows = rows.head(2)
    x = [0.04, 0.40, 0.54, 0.66, 0.79, 0.90]
    y = 0.16
    headers = ["Pareja", "Golpes", "W", "E", "W%", "E%"]
    for xi, header in zip(x, headers):
        ax.text(xi, y, header, fontsize=7, weight="bold", color=style["muted"], transform=ax.transAxes)
    for ridx, (_, row) in enumerate(rows.iterrows()):
        yy = y - 0.09 * (ridx + 1)
        values = [
            _shorten(_safe_get(row, "pareja", "N/D"), 24),
            _fmt_int(_safe_get(row, "total_golpes")),
            _fmt_int(_safe_get(row, "winners")),
            _fmt_int(_safe_get(row, "errores_totales")),
            _fmt_pct(_safe_get(row, "winner_pct")),
            _fmt_pct(_safe_get(row, "error_pct")),
        ]
        for xi, value in zip(x, values):
            ax.text(xi, yy, value, fontsize=7, color=style["text"], transform=ax.transAxes)


def _draw_player_card(
    ax: plt.Axes,
    player_row: pd.Series,
    pair_color: str,
    cluster_info: dict[int, str] | None = None,
) -> None:
    style = DEFAULT_STYLE
    _panel(ax, "", style, show_title=False)
    name = str(_safe_get(player_row, "jugador", _safe_get(player_row, "player", "N/D")))
    profile = _safe_get(player_row, "player_profile", "")
    cluster = _safe_get(player_row, "cluster", np.nan)
    if not profile and pd.notna(cluster) and cluster_info:
        profile = cluster_info.get(int(cluster), "")

    ax.add_patch(
        FancyBboxPatch(
            (0.02, 0.80),
            0.96,
            0.16,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            linewidth=0,
            facecolor=pair_color,
            transform=ax.transAxes,
        )
    )
    ax.text(0.18, 0.88, _shorten(name, 28), fontsize=10, weight="bold", color="white", transform=ax.transAxes)
    ax.add_patch(Circle((0.10, 0.88), 0.055, transform=ax.transAxes, facecolor="white", edgecolor="none", alpha=0.95))
    ax.text(0.10, 0.88, _initials(name), ha="center", va="center", fontsize=9, weight="bold", color=pair_color, transform=ax.transAxes)

    metrics = [
        ("W", _fmt_int(_safe_get(player_row, "winners"))),
        ("E", _fmt_int(_safe_get(player_row, "errores_totales"))),
        ("ENF", _fmt_int(_safe_get(player_row, "errores_no_forzados"))),
        ("P", _fmt_pct(_safe_get(player_row, "presion_ejercida_pct"))),
    ]
    xs = [0.10, 0.34, 0.58, 0.82]
    for x, (label, value) in zip(xs, metrics):
        ax.text(x, 0.68, label, ha="center", fontsize=7.5, color=style["muted"], transform=ax.transAxes)
        ax.text(x, 0.58, value, ha="center", fontsize=13, weight="bold", color=style["text"], transform=ax.transAxes)

    winner_pct = _to_float(_safe_get(player_row, "winner_pct"))
    error_pct = _to_float(_safe_get(player_row, "error_pct"))
    _draw_metric_donut(ax, 0.18, 0.34, winner_pct, error_pct)
    ax.add_patch(
        FancyBboxPatch(
            (0.34, 0.365),
            0.27,
            0.07,
            boxstyle="round,pad=0.008,rounding_size=0.015",
            linewidth=0,
            facecolor="#EAF2FF",
            transform=ax.transAxes,
        )
    )
    ax.add_patch(
        FancyBboxPatch(
            (0.34, 0.275),
            0.27,
            0.07,
            boxstyle="round,pad=0.008,rounding_size=0.015",
            linewidth=0,
            facecolor="#FDE8E2",
            transform=ax.transAxes,
        )
    )
    ax.text(0.365, 0.387, f"Winner% {_fmt_pct(winner_pct)}", fontsize=7.6, weight="bold", color=style["winner"], transform=ax.transAxes)
    ax.text(0.365, 0.297, f"Error% {_fmt_pct(error_pct)}", fontsize=7.6, weight="bold", color=style["error"], transform=ax.transAxes)

    bottom = [
        f"Golpes {_fmt_int(_safe_get(player_row, 'total_golpes'))}",
        f"Riesgo {_fmt_float(_safe_get(player_row, 'indice_riesgo'))}",
        f"Ef. ofensiva {_fmt_float(_safe_get(player_row, 'efectividad_ofensiva'))}",
    ]
    ax.text(0.05, 0.18, " | ".join(bottom), fontsize=7.3, color=style["text"], transform=ax.transAxes)
    cluster_text = f"Cluster {int(cluster)}" if pd.notna(cluster) else "Cluster N/D"
    profile_text = _wrap_text(str(profile), width=44, max_lines=2) if profile else "Perfil N/D"
    ax.add_patch(
        FancyBboxPatch(
            (0.04, 0.035),
            0.92,
            0.105,
            boxstyle="round,pad=0.008,rounding_size=0.016",
            linewidth=0.6,
            edgecolor=style["grid"],
            facecolor=style["soft_panel"],
            transform=ax.transAxes,
        )
    )
    ax.text(0.06, 0.105, cluster_text, fontsize=6.6, weight="bold", color=pair_color, transform=ax.transAxes)
    ax.text(0.22, 0.105, profile_text, fontsize=6.3, color=style["text"], va="top", linespacing=1.05, transform=ax.transAxes)


def _draw_pair_comparison(ax: plt.Axes, pair_metrics: pd.DataFrame) -> None:
    style = DEFAULT_STYLE
    _panel(ax, "Comparación entre parejas", style)
    if pair_metrics.empty:
        ax.text(0.5, 0.50, "N/D", ha="center", va="center", fontsize=18, color=style["muted"], transform=ax.transAxes)
        return

    metrics = [
        ("total_golpes", "Golpes", False),
        ("winners", "Winners", False),
        ("errores_totales", "Errores", False),
        ("errores_no_forzados", "ENF", False),
        ("winner_pct", "Winner%", True),
        ("error_pct", "Error%", True),
        ("presion_ejercida_pct", "Presion%", True),
    ]
    data = _ensure_numeric(pair_metrics, [m[0] for m in metrics])
    data = data.head(2)
    if len(data) == 1:
        data = pd.concat([data, pd.DataFrame([{"pareja": "N/D"}])], ignore_index=True)

    pair_a = data.iloc[0]
    pair_b = data.iloc[1]
    color_a, color_b = style["pair_colors"][:2]
    ax.text(0.22, 0.84, _shorten(_safe_get(pair_a, "pareja", "Pareja A"), 36), ha="center", fontsize=10.5, weight="bold", color=color_a, transform=ax.transAxes)
    ax.text(0.78, 0.84, _shorten(_safe_get(pair_b, "pareja", "Pareja B"), 36), ha="center", fontsize=10.5, weight="bold", color=color_b, transform=ax.transAxes)
    ax.plot([0.5, 0.5], [0.12, 0.80], color=style["grid"], lw=1, transform=ax.transAxes)

    for idx, (column, label, is_pct) in enumerate(metrics):
        y = 0.72 - idx * 0.085
        left = _to_float(_safe_get(pair_a, column))
        right = _to_float(_safe_get(pair_b, column))
        max_value = np.nanmax([left, right, 1.0])
        left_width = 0 if not np.isfinite(left) else 0.34 * left / max_value
        right_width = 0 if not np.isfinite(right) else 0.34 * right / max_value
        ax.barh(y, left_width, left=0.50 - left_width, height=0.032, color=color_a, alpha=0.82, transform=ax.transAxes)
        ax.barh(y, right_width, left=0.50, height=0.032, color=color_b, alpha=0.82, transform=ax.transAxes)
        ax.text(0.50, y + 0.018, label, ha="center", va="bottom", fontsize=7.2, weight="bold", color=style["muted"], transform=ax.transAxes)
        fmt = _fmt_pct if is_pct else _fmt_int
        ax.text(0.10, y, fmt(left), ha="left", va="center", fontsize=8, weight="bold", color=style["text"], transform=ax.transAxes)
        ax.text(0.90, y, fmt(right), ha="right", va="center", fontsize=8, weight="bold", color=style["text"], transform=ax.transAxes)


def _draw_evolution_or_scatter(
    ax: plt.Axes,
    actions: pd.DataFrame,
    player_metrics: pd.DataFrame,
    match_id: str,
) -> None:
    style = DEFAULT_STYLE
    _panel(ax, "Evolución aproximada", style)
    ordered = _ordered_actions(actions)
    if _has_reliable_timeline(actions) and not ordered.empty and "pareja" in ordered.columns:
        ordered = ordered.copy()
        ordered["contribucion"] = ordered.apply(_action_contribution, axis=1)
        ordered["event_index"] = range(1, len(ordered) + 1)
        pair_order = _ordered_pairs_from_players(player_metrics)
        pairs = [p for p in pair_order if p in set(ordered["pareja"].dropna().astype(str))]
        pairs.extend([p for p in ordered["pareja"].dropna().astype(str).unique().tolist() if p and p not in pairs])
        if pairs:
            for idx, pair in enumerate(pairs[:4]):
                subset = ordered[ordered["pareja"].astype(str) == pair].copy()
                subset["acumulado"] = subset["contribucion"].cumsum()
                if subset.empty:
                    continue
                ax.plot(
                    subset["event_index"],
                    subset["acumulado"],
                    lw=2.0,
                    color=style["pair_colors"][idx % len(style["pair_colors"])],
                    label=_shorten(pair, 28),
                )
            ax.set_xlabel("Orden de acciones analizables", fontsize=8)
            ax.set_ylabel("Contribución acumulada aprox.", fontsize=8)
            ax.legend(loc="upper left", bbox_to_anchor=(0.02, 0.90), fontsize=7, frameon=False)
            _style_chart_axis(ax, style)
            ax.margins(x=0.02, y=0.15)
            ax.text(
                0.99,
                0.02,
                "+1 winner | -1 error | +0.5 presión",
                ha="right",
                va="bottom",
                fontsize=7,
                color=style["muted"],
                transform=ax.transAxes,
            )
            return

    _draw_fallback_chart_if_no_timeline(ax, player_metrics, style)


def _draw_fallback_chart_if_no_timeline(
    ax: plt.Axes,
    player_metrics: pd.DataFrame,
    style: dict[str, Any],
) -> None:
    metrics = _ensure_numeric(player_metrics, ["winner_pct", "error_pct", "total_golpes"])
    if not metrics.empty and {"winner_pct", "error_pct"}.issubset(metrics.columns):
        pair_values = _ordered_pairs_from_players(metrics)
        colors = {pair: style["pair_colors"][idx % len(style["pair_colors"])] for idx, pair in enumerate(pair_values)}
        for _, row in metrics.iterrows():
            pair = str(_safe_get(row, "pareja", ""))
            size = max(40, _to_float(_safe_get(row, "total_golpes")) * 0.4)
            x = _to_float(_safe_get(row, "winner_pct"))
            y = _to_float(_safe_get(row, "error_pct"))
            if not np.isfinite(x) or not np.isfinite(y):
                continue
            ax.scatter(
                x,
                y,
                s=size,
                color=colors.get(pair, style["neutral"]),
                alpha=0.78,
                edgecolor="white",
                linewidth=1,
            )
            ax.text(x, y, _shorten(str(_safe_get(row, "jugador", "")), 14), fontsize=7)
        ax.set_xlabel("Winner%", fontsize=8)
        ax.set_ylabel("Error%", fontsize=8)
        _style_chart_axis(ax, style)
        ax.margins(x=0.15, y=0.20)
        ax.text(
            0.99,
            0.02,
            "Vista alternativa por falta de secuencia temporal fiable",
            ha="right",
            va="bottom",
            fontsize=7,
            color=style["muted"],
            transform=ax.transAxes,
        )
        return

    metrics = _ensure_numeric(player_metrics, ["efectividad_ofensiva", "indice_riesgo"])
    if not metrics.empty and {"efectividad_ofensiva", "indice_riesgo"}.issubset(metrics.columns):
        labels = [_shorten(_safe_get(row, "jugador", "N/D"), 13) for _, row in metrics.iterrows()]
        x = np.arange(len(metrics))
        ax.bar(x - 0.18, pd.to_numeric(metrics["efectividad_ofensiva"], errors="coerce").fillna(0), width=0.36, label="Ef. ofensiva", color=style["winner"], alpha=0.75)
        ax.bar(x + 0.18, pd.to_numeric(metrics["indice_riesgo"], errors="coerce").fillna(0), width=0.36, label="Riesgo", color=style["error"], alpha=0.75)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=20, ha="right")
        ax.legend(loc="upper left", fontsize=7, frameon=False)
        _style_chart_axis(ax, style)
        ax.text(0.99, 0.02, "Vista alternativa por falta de secuencia temporal fiable", ha="right", va="bottom", fontsize=7, color=style["muted"], transform=ax.transAxes)
        return

    if metrics.empty:
        ax.text(0.5, 0.5, "N/D", ha="center", va="center", fontsize=18, color=style["muted"], transform=ax.transAxes)
        return


def _draw_recommendations(
    ax: plt.Axes,
    recommendations: pd.DataFrame,
    cards: pd.DataFrame | None = None,
) -> None:
    style = DEFAULT_STYLE
    _panel(ax, "Orientaciones destacadas", style)
    rows = _recommendation_rows(recommendations, cards)
    if not rows:
        ax.text(0.5, 0.48, "N/D", ha="center", va="center", fontsize=18, color=style["muted"], transform=ax.transAxes)
        return
    slots = [(0.675, 0.205), (0.425, 0.205), (0.175, 0.205)]
    for idx, (item, (y, height)) in enumerate(zip(rows[:3], slots), start=1):
        _draw_recommendation_item(ax, idx, item, y, height, style)
    if len(rows) > 3:
        ax.text(
            0.95,
            0.035,
            f"+{len(rows) - 3} en CSV",
            ha="right",
            va="bottom",
            fontsize=5.6,
            color=style["muted"],
            transform=ax.transAxes,
        )


def _draw_recommendation_item(
    ax: plt.Axes,
    idx: int,
    item: dict[str, str],
    y: float,
    height: float,
    style: dict[str, Any],
) -> None:
    x0 = 0.045
    y0 = y - height / 2
    ax.add_patch(
        FancyBboxPatch(
            (x0, y0),
            0.91,
            height,
            boxstyle="round,pad=0.010,rounding_size=0.018",
            linewidth=0.7,
            edgecolor=style["grid"],
            facecolor=style["soft_panel"],
            transform=ax.transAxes,
        )
    )
    badge_x = x0 + 0.045
    badge_y = y0 + height - 0.045
    ax.add_patch(
        Circle(
            (badge_x, badge_y),
            0.027,
            transform=ax.transAxes,
            facecolor=style["pair_colors"][0],
            edgecolor="none",
        )
    )
    ax.text(
        badge_x,
        badge_y,
        str(idx),
        ha="center",
        va="center",
        fontsize=7,
        color="white",
        weight="bold",
        transform=ax.transAxes,
    )

    text_x = x0 + 0.088
    target = _wrap_text(item.get("target", "N/D"), width=26, max_lines=1)
    evidence = _truncate_text(item.get("evidence", ""), 46)
    recommendation = _wrap_text(item.get("recommendation", "N/D"), width=48, max_lines=1)

    ax.text(
        text_x,
        y0 + height - 0.032,
        target,
        fontsize=7.1,
        weight="bold",
        color=style["text"],
        transform=ax.transAxes,
    )
    ax.text(
        text_x,
        y0 + height - 0.088,
        recommendation,
        fontsize=5.6,
        color=style["text"],
        va="top",
        transform=ax.transAxes,
    )
    if evidence:
        ax.text(
            text_x,
            y0 + 0.030,
            evidence,
            fontsize=5.1,
            color=style["muted"],
            transform=ax.transAxes,
        )


def _safe_get(row: Any, col: str, default: Any = np.nan) -> Any:
    if row is None:
        return default
    try:
        value = row[col]
    except (KeyError, TypeError, IndexError):
        return default
    if isinstance(value, float) and np.isnan(value):
        return default
    if pd.isna(value):
        return default
    return value


def _fmt_int(x: Any) -> str:
    value = _to_float(x)
    return "N/D" if not np.isfinite(value) else f"{int(round(value)):,}".replace(",", ".")


def _fmt_float(x: Any, digits: int = 2) -> str:
    value = _to_float(x)
    return "N/D" if not np.isfinite(value) else f"{value:.{digits}f}"


def _fmt_pct(x: Any) -> str:
    value = _to_float(x)
    return "N/D" if not np.isfinite(value) else f"{value:.1f}%"


def _shorten(text: Any, max_len: int = 80) -> str:
    return _truncate_text(text, max_len)


def _truncate_text(text: Any, max_len: int = 80) -> str:
    text = "" if pd.isna(text) else str(text)
    text = " ".join(text.split())
    if len(text) <= max_len:
        return text
    return text[: max(0, max_len - 3)].rstrip() + "..."


def _wrap_text(text: Any, width: int = 40, max_lines: int = 2) -> str:
    clean = "" if pd.isna(text) else " ".join(str(text).split())
    if not clean:
        return ""
    wrapped = fill(clean, width=width, break_long_words=False, replace_whitespace=False).splitlines()
    if len(wrapped) <= max_lines:
        return "\n".join(wrapped)
    kept = wrapped[:max_lines]
    kept[-1] = _truncate_text(kept[-1], max(8, width - 3))
    return "\n".join(kept)


def _initials(name: Any) -> str:
    parts = [part for part in str(name).replace("-", " ").split() if part]
    if not parts:
        return "ND"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _ensure_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def _find_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for col in candidates:
        if col in df.columns:
            return col
    return None


def _match_ids_from_data(data: dict[str, pd.DataFrame]) -> list[str]:
    metadata = data.get("metadata", pd.DataFrame())
    if "match_id" in metadata.columns and not metadata.empty:
        return metadata["match_id"].dropna().astype(str).drop_duplicates().tolist()
    ids: list[str] = []
    for key in ["player_match_metrics", "pair_match_metrics", "actions_clean", "recommendations"]:
        df = data.get(key, pd.DataFrame())
        if "match_id" in df.columns:
            ids.extend(df["match_id"].dropna().astype(str).tolist())
    return sorted(dict.fromkeys(ids))


def _match_filter(df: pd.DataFrame, match_id: str) -> pd.DataFrame:
    if df is None or df.empty or "match_id" not in df.columns:
        return pd.DataFrame()
    return df[df["match_id"].astype(str) == str(match_id)].copy()


def _first_row(df: pd.DataFrame) -> pd.Series | None:
    return None if df.empty else df.iloc[0]


def _panel(ax: plt.Axes, title: str, style: dict[str, Any], show_title: bool = True) -> None:
    ax.set_axis_off()
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.add_patch(
        FancyBboxPatch(
            (0.01, 0.01),
            0.98,
            0.98,
            boxstyle="round,pad=0.012,rounding_size=0.025",
            linewidth=0.8,
            edgecolor=style["grid"],
            facecolor=style["panel"],
            transform=ax.transAxes,
            zorder=-1,
        )
    )
    if show_title:
        ax.text(0.04, 0.92, title, fontsize=10, weight="bold", color=style["text"], transform=ax.transAxes)


def _draw_action_summary(
    ax: plt.Axes,
    actions: pd.DataFrame,
    player_metrics: pd.DataFrame,
    cluster_info: dict[int, str],
    pair_colors: dict[str, str],
    style: dict[str, Any],
) -> None:
    _panel(ax, "Últimas acciones", style)
    ordered = _ordered_actions(actions)
    last = ordered.tail(10) if not ordered.empty else pd.DataFrame()
    if last.empty:
        ax.text(0.5, 0.50, "N/D", ha="center", va="center", fontsize=18, color=style["muted"], transform=ax.transAxes)
    else:
        for idx, (_, row) in enumerate(last.iterrows()):
            x = 0.08 + idx * 0.092
            pair = str(_safe_get(row, "pareja", ""))
            label, edge = _action_label(row)
            ax.add_patch(
                Circle(
                    (x, 0.58),
                    0.034,
                    transform=ax.transAxes,
                    facecolor=pair_colors.get(pair, style["neutral"]),
                    edgecolor=edge,
                    linewidth=1.2,
                    alpha=0.88,
                )
            )
            ax.text(x, 0.58, label, ha="center", va="center", fontsize=6.2, color="white", weight="bold", transform=ax.transAxes)
        ax.text(0.05, 0.44, "W = winner   E = error   P = presión   O = otras", fontsize=6.6, color=style["muted"], transform=ax.transAxes)

    winners = int(pd.to_numeric(player_metrics.get("winners", pd.Series(dtype=float)), errors="coerce").sum())
    errors = int(pd.to_numeric(player_metrics.get("errores_totales", pd.Series(dtype=float)), errors="coerce").sum())
    pressure = pd.to_numeric(player_metrics.get("presion_ejercida_pct", pd.Series(dtype=float)), errors="coerce").mean()
    clusters = player_metrics["cluster"].dropna().nunique() if "cluster" in player_metrics.columns else 0
    ax.text(0.05, 0.26, f"W/E total: {winners}/{errors}", fontsize=8.2, weight="bold", color=style["text"], transform=ax.transAxes)
    ax.text(0.05, 0.15, f"Presión media: {_fmt_pct(pressure)}", fontsize=7.5, color=style["text"], transform=ax.transAxes)
    ax.text(0.05, 0.06, f"Clusters presentes: {_fmt_int(clusters)}", fontsize=7.5, color=style["text"], transform=ax.transAxes)


def _player_rows_for_match(data: dict[str, pd.DataFrame], match_id: str) -> pd.DataFrame:
    player_metrics = _match_filter(data.get("player_match_metrics", pd.DataFrame()), match_id)
    clusters = _match_filter(data.get("player_match_clusters", pd.DataFrame()), match_id)
    if not clusters.empty and "cluster" in clusters.columns:
        player_metrics = clusters.copy()

    cards = _match_filter(data.get("player_recommendation_cards", pd.DataFrame()), match_id)
    if not player_metrics.empty and not cards.empty and {"player", "match_id"}.issubset(cards.columns):
        card_cols = [
            col
            for col in ["player", "player_profile", "priority_label", "priority_score", "formatted_evidence", "main_recommendation"]
            if col in cards.columns
        ]
        card_subset = cards[card_cols].drop_duplicates(subset=["player"]).rename(columns={"player": "jugador"})
        player_metrics = player_metrics.merge(card_subset, on="jugador", how="left")
    return player_metrics


def _select_player_cards(player_metrics: pd.DataFrame) -> pd.DataFrame:
    if player_metrics.empty:
        return player_metrics
    data = _ensure_numeric(player_metrics, ["total_golpes"])
    if len(data) <= 4:
        return data
    if "total_golpes" in data.columns:
        top = data.sort_values("total_golpes", ascending=False).head(4).copy()
    else:
        top = data.head(4).copy()
    pair_order = _ordered_pairs_from_players(data)
    order = {pair: idx for idx, pair in enumerate(pair_order)}
    top["_pair_order"] = top.get("pareja", pd.Series(dtype=str)).astype(str).map(order).fillna(len(order))
    sort_cols = ["_pair_order"] + (["total_golpes"] if "total_golpes" in top.columns else [])
    ascending = [True] + ([False] if "total_golpes" in top.columns else [])
    top = top.sort_values(sort_cols, ascending=ascending)
    return top.drop(columns=["_pair_order"])


def _draw_empty_player_card(ax: plt.Axes, style: dict[str, Any]) -> None:
    _panel(ax, "", style, show_title=False)
    ax.add_patch(Circle((0.5, 0.58), 0.10, transform=ax.transAxes, facecolor=style["grid"], edgecolor="none"))
    ax.text(0.5, 0.58, "N/D", ha="center", va="center", fontsize=11, weight="bold", color=style["muted"], transform=ax.transAxes)
    ax.text(0.5, 0.36, "Jugador no disponible", ha="center", fontsize=8, color=style["muted"], transform=ax.transAxes)


def _draw_metric_donut(ax: plt.Axes, x: float, y: float, winner_pct: float, error_pct: float) -> None:
    style = DEFAULT_STYLE
    winner_value = max(winner_pct, 0) if np.isfinite(winner_pct) else 0
    error_value = max(error_pct, 0) if np.isfinite(error_pct) else 0
    total = max(winner_value + error_value, 1.0)
    winner_angle = 360 * winner_value / total
    error_angle = 360 * error_value / total
    ax.add_patch(Wedge((x, y), 0.115, 0, 360, width=0.035, transform=ax.transAxes, facecolor=style["grid"], edgecolor="none"))
    ax.add_patch(Wedge((x, y), 0.115, 90, 90 + winner_angle, width=0.035, transform=ax.transAxes, facecolor=style["winner"], edgecolor="none"))
    ax.add_patch(Wedge((x, y), 0.115, 90 + winner_angle, 90 + winner_angle + error_angle, width=0.035, transform=ax.transAxes, facecolor=style["error"], edgecolor="none"))
    ax.text(x, y, "W/E", ha="center", va="center", fontsize=7, color=style["muted"], transform=ax.transAxes)


def _pair_color_map(match_meta: pd.Series | None, pair_metrics: pd.DataFrame, style: dict[str, Any]) -> dict[str, str]:
    pairs: list[str] = []
    for col in ["pair_1", "pair_2"]:
        value = _safe_get(match_meta, col, "")
        if value:
            pairs.append(str(value))
    if "pareja" in pair_metrics.columns:
        pairs.extend(pair_metrics["pareja"].dropna().astype(str).tolist())
    unique = list(dict.fromkeys([pair for pair in pairs if pair and pair != "N/D"]))
    return {pair: style["pair_colors"][idx % len(style["pair_colors"])] for idx, pair in enumerate(unique)}


def _sort_pair_metrics_by_pair(pair_metrics: pd.DataFrame, pair_order: list[str]) -> pd.DataFrame:
    if pair_metrics.empty or "pareja" not in pair_metrics.columns:
        return pair_metrics
    order = {pair: idx for idx, pair in enumerate(pair_order)}
    out = pair_metrics.copy()
    out["_pair_order"] = out["pareja"].astype(str).map(order).fillna(len(order))
    if "total_golpes" in out.columns:
        out["_volume"] = pd.to_numeric(out["total_golpes"], errors="coerce").fillna(0)
        out = out.sort_values(["_pair_order", "_volume"], ascending=[True, False])
        return out.drop(columns=["_pair_order", "_volume"])
    out = out.sort_values("_pair_order")
    return out.drop(columns=["_pair_order"])


def _sort_players_by_pair(
    player_metrics: pd.DataFrame,
    match_meta: pd.Series | None,
    pair_metrics: pd.DataFrame,
) -> pd.DataFrame:
    if player_metrics.empty or "pareja" not in player_metrics.columns:
        return player_metrics
    pair_order: list[str] = []
    for col in ["pair_1", "pair_2"]:
        value = _safe_get(match_meta, col, "")
        if value:
            pair_order.append(str(value))
    if not pair_order and "pareja" in pair_metrics.columns:
        pair_order.extend(pair_metrics["pareja"].dropna().astype(str).tolist())
    pair_order = list(dict.fromkeys(pair_order))
    order = {pair: idx for idx, pair in enumerate(pair_order)}
    out = _ensure_numeric(player_metrics, ["total_golpes"]).copy()
    out["_pair_order"] = out["pareja"].astype(str).map(order).fillna(len(order))
    if "total_golpes" in out.columns:
        out["_volume"] = out["total_golpes"].fillna(0)
        out = out.sort_values(["_pair_order", "_volume", "jugador"], ascending=[True, False, True])
        return out.drop(columns=["_pair_order", "_volume"])
    out = out.sort_values(["_pair_order", "jugador"])
    return out.drop(columns=["_pair_order"])


def _cluster_profile_map(cluster_profiles: pd.DataFrame) -> dict[int, str]:
    if cluster_profiles.empty or not {"cluster", "profile_interpretation"}.issubset(cluster_profiles.columns):
        return {}
    mapping: dict[int, str] = {}
    for _, row in cluster_profiles.iterrows():
        cluster = _to_float(_safe_get(row, "cluster"))
        if np.isfinite(cluster):
            mapping[int(cluster)] = str(_safe_get(row, "profile_interpretation", ""))
    return mapping


def _ordered_actions(actions: pd.DataFrame) -> pd.DataFrame:
    if actions.empty:
        return pd.DataFrame()
    order_col = _find_col(actions, ["clip_start", "raw_row_number", "golpe_q_tiempo", "jugador_tiempo"])
    out = actions.copy()
    if order_col is not None:
        out["_order"] = pd.to_numeric(out[order_col], errors="coerce")
        if out["_order"].notna().sum() >= max(3, len(out) * 0.25):
            return out.sort_values(["_order"], kind="stable").drop(columns=["_order"])
    return out.reset_index(drop=True)


def _has_reliable_timeline(actions: pd.DataFrame) -> bool:
    if actions.empty:
        return False
    order_col = _find_col(actions, ["clip_start", "raw_row_number", "golpe_q_tiempo", "jugador_tiempo"])
    if order_col is None:
        return False
    values = pd.to_numeric(actions[order_col], errors="coerce")
    return bool(values.notna().sum() >= max(10, len(actions) * 0.25) and values.nunique(dropna=True) >= 10)


def _ordered_pairs_from_players(player_metrics: pd.DataFrame) -> list[str]:
    if player_metrics.empty or "pareja" not in player_metrics.columns:
        return []
    return [
        str(pair)
        for pair in player_metrics["pareja"].dropna().astype(str).drop_duplicates().tolist()
        if pair and pair != "N/D"
    ]


def _action_label(row: pd.Series) -> tuple[str, str]:
    style = DEFAULT_STYLE
    if _as_bool(_safe_get(row, "es_winner", False)):
        return "W", style["winner"]
    if _as_bool(_safe_get(row, "es_fuerza_error", False)):
        return "P", style["pressure"]
    if _as_bool(_safe_get(row, "es_error", False)):
        return "E", style["error"]
    return "O", style["neutral"]


def _action_contribution(row: pd.Series) -> float:
    if _as_bool(_safe_get(row, "es_winner", False)):
        return 1.0
    if _as_bool(_safe_get(row, "es_fuerza_error", False)):
        return 0.5
    if _as_bool(_safe_get(row, "es_error", False)):
        return -1.0
    return 0.0


def _recommendation_rows(recommendations: pd.DataFrame, cards: pd.DataFrame | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if cards is not None and not cards.empty:
        data = cards.copy()
        data["_priority"] = data.get("priority_label", "").map(PRIORITY_ORDER).fillna(0)
        if "priority_score" in data.columns:
            data["priority_score"] = pd.to_numeric(data["priority_score"], errors="coerce").fillna(0)
        else:
            data["priority_score"] = 0
        data = data.sort_values(["_priority", "priority_score"], ascending=False)
        for _, row in data.iterrows():
            rows.append(
                {
                    "target": str(_safe_get(row, "player", "N/D")),
                    "rule": str(_safe_get(row, "rules_triggered", _safe_get(row, "player_profile", "N/D"))),
                    "evidence": str(_safe_get(row, "formatted_evidence", _safe_get(row, "priority_label", ""))),
                    "recommendation": str(_safe_get(row, "main_recommendation", "N/D")),
                }
            )
    if len(rows) < 3 and recommendations is not None and not recommendations.empty:
        data = recommendations.copy()
        if "scope" in data.columns:
            data["_scope_order"] = data["scope"].map({"player": 2, "pair": 1}).fillna(0)
            data = data.sort_values("_scope_order", ascending=False)
        for _, row in data.iterrows():
            rows.append(
                {
                    "target": str(_safe_get(row, "target", "N/D")),
                    "rule": f"{_safe_get(row, 'rule_applied', 'N/D')} | {_safe_get(row, 'evidence_metric', '')}={_safe_get(row, 'evidence_value', '')}",
                    "evidence": f"{_safe_get(row, 'evidence_metric', '')}: {_safe_get(row, 'evidence_value', '')}",
                    "recommendation": str(_safe_get(row, "recommendation", "N/D")),
                }
            )
            if len(rows) >= 3:
                break
    return rows


def _sum_col(primary: pd.DataFrame, column: str, fallback: pd.DataFrame | None = None) -> float:
    if column in primary.columns:
        return float(pd.to_numeric(primary[column], errors="coerce").sum())
    if fallback is not None and column in fallback.columns:
        return float(pd.to_numeric(fallback[column], errors="coerce").sum())
    return np.nan


def _to_float(value: Any) -> float:
    try:
        number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    except Exception:
        return np.nan
    return float(number) if pd.notna(number) else np.nan


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    text = str(value).strip().lower()
    return text in {"true", "1", "yes", "si", "sí"}


def _style_chart_axis(ax: plt.Axes, style: dict[str, Any]) -> None:
    ax.set_axis_on()
    ax.set_autoscale_on(True)
    ax.set_facecolor(style["panel"])
    ax.grid(True, color=style["grid"], linewidth=0.8, alpha=0.8)
    ax.tick_params(axis="both", labelsize=7, colors=style["muted"])
    for spine in ax.spines.values():
        spine.set_color(style["grid"])
    ax.relim()
    ax.autoscale_view()
