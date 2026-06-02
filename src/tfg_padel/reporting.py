from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from . import config
from .clustering import run_player_match_clustering
from .io import read_csv_if_exists, write_csv
from .recommender import generate_recommendations
from .recommendations_reporting import write_recommendations_summary


def build_dataset_summary(
    metadata: pd.DataFrame,
    raw_report: pd.DataFrame,
    matches_clean: pd.DataFrame,
    actions_clean: pd.DataFrame,
    duplicates_collapsed: int,
) -> pd.DataFrame:
    players = actions_clean["jugador"].dropna().nunique() if "jugador" in actions_clean.columns else 0
    pairs = actions_clean["pareja"].dropna().nunique() if "pareja" in actions_clean.columns else 0
    rows = [
        ("partidos_principales", len(metadata), "Partidos definidos en data/metadata/matches_metadata.csv."),
        ("csv_raw_leidos_ok", int((raw_report["status"] == "ok").sum()) if "status" in raw_report.columns else 0, ""),
        ("csv_raw_con_error", int((raw_report["status"] != "ok").sum()) if "status" in raw_report.columns else 0, ""),
        ("filas_raw", int(raw_report["rows"].sum()) if "rows" in raw_report.columns else 0, ""),
        ("filas_limpias", len(matches_clean), "Tras normalizacion y colapsado de eventos."),
        ("acciones_analizables", len(actions_clean), "Filas con golpe_q y jugador."),
        ("jugadores_distintos", int(players), ""),
        ("parejas_distintas", int(pairs), ""),
        ("eventos_colapsados", int(duplicates_collapsed), "Diferencia entre filas raw y eventos colapsados."),
        ("ficheros_excluidos", ", ".join(config.EXCLUDED_RAW_FILES), "No se usan para metricas principales."),
    ]
    return pd.DataFrame(rows, columns=["metric", "value", "notes"])


def build_matches_summary(metadata: pd.DataFrame, matches_clean: pd.DataFrame, actions_clean: pd.DataFrame) -> pd.DataFrame:
    clean_counts = (
        matches_clean.groupby("match_id").size().rename("filas_limpias").reset_index()
        if not matches_clean.empty
        else pd.DataFrame(columns=["match_id", "filas_limpias"])
    )
    action_counts = (
        actions_clean.groupby("match_id").size().rename("acciones_analizables").reset_index()
        if not actions_clean.empty
        else pd.DataFrame(columns=["match_id", "acciones_analizables"])
    )
    out = metadata.merge(clean_counts, on="match_id", how="left").merge(action_counts, on="match_id", how="left")
    out[["filas_limpias", "acciones_analizables"]] = out[
        ["filas_limpias", "acciones_analizables"]
    ].fillna(0).astype(int)
    return out


def _save_plot(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(path, dpi=300, bbox_inches="tight")
    plt.close()


def _warn(warnings: list[str], message: str) -> None:
    warnings.append(message)
    print(f"WARNING: {message}")


def generate_figures() -> list[str]:
    config.ensure_directories()
    warnings: list[str] = []
    sns.set_theme(style="whitegrid", palette="Set2")

    player_global = read_csv_if_exists(config.TABLES_DIR / "player_global_metrics.csv")
    pair_global = read_csv_if_exists(config.TABLES_DIR / "pair_global_metrics.csv")
    player_match = read_csv_if_exists(config.PROCESSED_DIR / "player_match_metrics.csv")
    pair_match = read_csv_if_exists(config.PROCESSED_DIR / "pair_match_metrics.csv")
    actions = read_csv_if_exists(config.PROCESSED_DIR / "actions_clean.csv")
    clusters = read_csv_if_exists(config.TABLES_DIR / "player_match_clusters.csv")

    if player_global.empty:
        _warn(warnings, "No se genera golpes_por_jugador.png: falta player_global_metrics.csv.")
    else:
        data = player_global.sort_values("total_golpes", ascending=False)
        plt.figure(figsize=(10, 5))
        sns.barplot(data=data, x="jugador", y="total_golpes")
        plt.title("Golpes por jugador")
        plt.xlabel("Jugador")
        plt.ylabel("Total de golpes")
        plt.xticks(rotation=35, ha="right")
        _save_plot(config.FIGURES_DIR / "golpes_por_jugador.png")

        melt = data.melt(
            id_vars=["jugador"],
            value_vars=[c for c in ["winner_pct", "error_pct"] if c in data.columns],
            var_name="metrica",
            value_name="porcentaje",
        )
        plt.figure(figsize=(10, 5))
        sns.barplot(data=melt, x="jugador", y="porcentaje", hue="metrica")
        plt.title("Winner % y error % por jugador")
        plt.xlabel("Jugador")
        plt.ylabel("Porcentaje")
        plt.xticks(rotation=35, ha="right")
        _save_plot(config.FIGURES_DIR / "winner_error_jugador.png")

        metric_cols = [c for c in ["winner_pct", "error_pct", "presion_ejercida_pct"] if c in data.columns]
        melt = data.melt(id_vars=["jugador"], value_vars=metric_cols, var_name="metrica", value_name="valor")
        plt.figure(figsize=(11, 5))
        sns.barplot(data=melt, x="jugador", y="valor", hue="metrica")
        plt.title("Metricas globales por jugador")
        plt.xlabel("Jugador")
        plt.ylabel("Valor")
        plt.xticks(rotation=35, ha="right")
        _save_plot(config.FIGURES_DIR / "metricas_globales_jugador.png")

    if player_match.empty:
        _warn(warnings, "No se genera riesgo_efectividad.png: falta player_match_metrics.csv.")
    else:
        plt.figure(figsize=(9, 5.5))
        sns.scatterplot(
            data=player_match,
            x="indice_riesgo",
            y="efectividad_ofensiva",
            hue="pareja",
            s=80,
            marker="o",
            edgecolor="black",
            linewidth=0.35,
            alpha=0.85,
        )
        plt.title("Riesgo y efectividad ofensiva por jugador-partido")
        plt.xlabel("Índice de riesgo")
        plt.ylabel("Efectividad ofensiva")
        plt.grid(True, alpha=0.25, linewidth=0.6)
        plt.legend(title="Pareja", bbox_to_anchor=(1.02, 1), loc="upper left", borderaxespad=0)
        _save_plot(config.FIGURES_DIR / "riesgo_efectividad.png")

    if clusters.empty:
        if not player_match.empty:
            _, clusters, _, cluster_warnings = run_player_match_clustering(player_match)
            warnings.extend(cluster_warnings)
    cluster_plot_columns = {"winner_pct", "error_pct", "cluster"}
    missing_cluster_plot_columns = sorted(cluster_plot_columns - set(clusters.columns))
    if clusters.empty or missing_cluster_plot_columns:
        _warn(warnings, "No se genera clustering_jugadores.png: faltan clusters.")
    else:
        plot_data = clusters.copy()
        plot_data["cluster"] = plot_data["cluster"].astype(str)
        cluster_order = sorted(
            plot_data["cluster"].dropna().unique(),
            key=lambda value: (
                not str(value).lstrip("-").isdigit(),
                int(value) if str(value).lstrip("-").isdigit() else str(value),
            ),
        )
        plt.figure(figsize=(9, 5.5))
        sns.scatterplot(
            data=plot_data,
            x="winner_pct",
            y="error_pct",
            hue="cluster",
            hue_order=cluster_order,
            s=80,
            palette="Set2",
            edgecolor="black",
            linewidth=0.4,
            alpha=0.9,
        )
        plt.title("Clusters jugador--partido")
        plt.xlabel("Winner %")
        plt.ylabel("Error %")
        plt.legend(title="Cluster", frameon=True)
        _save_plot(config.FIGURES_DIR / "clustering_jugadores.png")

    if pair_global.empty:
        _warn(warnings, "No se genera errores_por_pareja.png: falta pair_global_metrics.csv.")
    else:
        data = pair_global.sort_values("error_pct", ascending=False)
        plt.figure(figsize=(9, 5))
        sns.barplot(data=data, x="pareja", y="error_pct")
        plt.title("Error % por pareja")
        plt.xlabel("Pareja")
        plt.ylabel("Error %")
        plt.xticks(rotation=25, ha="right")
        _save_plot(config.FIGURES_DIR / "errores_por_pareja.png")

        metric_cols = [c for c in ["winner_pct", "error_pct"] if c in data.columns]
        melt = data.melt(id_vars=["pareja"], value_vars=metric_cols, var_name="metrica", value_name="valor")
        plt.figure(figsize=(9, 5))
        sns.barplot(data=melt, x="pareja", y="valor", hue="metrica")
        plt.title("Winner % y error % por pareja")
        plt.xlabel("Pareja")
        plt.ylabel("Porcentaje")
        plt.xticks(rotation=25, ha="right")
        _save_plot(config.FIGURES_DIR / "error_winner_por_pareja.png")

    if actions.empty:
        _warn(warnings, "No se genera golpes_por_partido.png: falta actions_clean.csv.")
    else:
        counts = actions.groupby("match_id").size().reset_index(name="acciones_analizables")
        plt.figure(figsize=(11, 5))
        sns.barplot(data=counts, x="match_id", y="acciones_analizables")
        plt.title("Acciones analizables por partido")
        plt.xlabel("Partido")
        plt.ylabel("Acciones analizables")
        plt.xticks(rotation=35, ha="right")
        _save_plot(config.FIGURES_DIR / "golpes_por_partido.png")

    return warnings


def ensure_recommendations() -> pd.DataFrame:
    recommendations = read_csv_if_exists(config.TABLES_DIR / "recommendations.csv")
    if not recommendations.empty:
        return recommendations

    player_metrics = read_csv_if_exists(config.PROCESSED_DIR / "player_match_metrics.csv")
    pair_metrics = read_csv_if_exists(config.PROCESSED_DIR / "pair_match_metrics.csv")
    recommendations = generate_recommendations(player_metrics, pair_metrics)
    write_csv(recommendations, config.TABLES_DIR / "recommendations.csv")
    return recommendations


def generate_latex_ready_tables() -> list[str]:
    config.ensure_directories()
    warnings: list[str] = []
    recommendations = ensure_recommendations()

    mapping = {
        "latex_dataset_summary.csv": config.TABLES_DIR / "dataset_summary.csv",
        "latex_quality_summary.csv": config.TABLES_DIR / "data_quality_summary.csv",
        "latex_player_metrics.csv": config.PROCESSED_DIR / "player_match_metrics.csv",
        "latex_pair_metrics.csv": config.PROCESSED_DIR / "pair_match_metrics.csv",
        "latex_cluster_profiles.csv": config.TABLES_DIR / "cluster_profiles.csv",
    }

    metadata = read_csv_if_exists(config.MATCHES_METADATA_PATH)
    matches_clean = read_csv_if_exists(config.PROCESSED_DIR / "matches_clean.csv")
    actions_clean = read_csv_if_exists(config.PROCESSED_DIR / "actions_clean.csv")
    if not metadata.empty:
        matches_summary = build_matches_summary(metadata, matches_clean, actions_clean)
        write_csv(matches_summary, config.TABLES_DIR / "latex_matches_summary.csv")
    else:
        warnings.append("No se pudo generar latex_matches_summary.csv: falta metadata.")

    for target_name, source in mapping.items():
        df = read_csv_if_exists(source)
        if df.empty:
            warnings.append(f"No se pudo generar {target_name}: falta {source.name} o esta vacio.")
            write_csv(pd.DataFrame(), config.TABLES_DIR / target_name)
            continue
        write_csv(df, config.TABLES_DIR / target_name)

    write_csv(recommendations, config.TABLES_DIR / "latex_recommendations.csv")
    write_recommendations_summary(recommendations)
    write_latex_versions()
    return warnings


def write_latex_versions() -> None:
    config.LATEX_TABLES_DIR.mkdir(parents=True, exist_ok=True)
    for csv_path in config.TABLES_DIR.glob("latex_*.csv"):
        df = pd.read_csv(csv_path)
        tex_path = config.LATEX_TABLES_DIR / f"{csv_path.stem}.tex"
        if df.empty:
            tex_path.write_text("% Tabla vacia: datos insuficientes.\n", encoding="utf-8")
        else:
            tex_path.write_text(
                df.to_latex(index=False, escape=True, longtable=True),
                encoding="utf-8",
            )
