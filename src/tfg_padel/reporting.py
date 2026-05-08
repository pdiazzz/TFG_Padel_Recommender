from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from . import config
from .clustering import run_player_match_clustering
from .io import read_csv_if_exists, write_csv
from .recommender import generate_recommendations


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
        plt.figure(figsize=(8, 5))
        sns.scatterplot(
            data=player_match,
            x="indice_riesgo",
            y="efectividad_ofensiva",
            hue="pareja",
            style="tournament",
            s=80,
        )
        plt.title("Riesgo y efectividad ofensiva por jugador-partido")
        plt.xlabel("Indice de riesgo")
        plt.ylabel("Efectividad ofensiva")
        _save_plot(config.FIGURES_DIR / "riesgo_efectividad.png")

    if clusters.empty:
        if not player_match.empty:
            _, clusters, _, cluster_warnings = run_player_match_clustering(player_match)
            warnings.extend(cluster_warnings)
    if clusters.empty or "cluster" not in clusters.columns:
        _warn(warnings, "No se genera clustering_jugadores.png: faltan clusters.")
    else:
        plt.figure(figsize=(8, 5))
        sns.scatterplot(
            data=clusters,
            x="winner_pct",
            y="error_pct",
            hue="cluster",
            style="pareja",
            s=80,
            palette="Set2",
        )
        plt.title("Clusters jugador-partido")
        plt.xlabel("Winner %")
        plt.ylabel("Error %")
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


def write_memoria_updates() -> None:
    dataset = read_csv_if_exists(config.TABLES_DIR / "dataset_summary.csv")
    player_metrics = read_csv_if_exists(config.PROCESSED_DIR / "player_match_metrics.csv")
    pair_metrics = read_csv_if_exists(config.PROCESSED_DIR / "pair_match_metrics.csv")
    cluster_profiles = read_csv_if_exists(config.TABLES_DIR / "cluster_profiles.csv")

    def table_preview(df: pd.DataFrame, n: int = 8) -> str:
        if df.empty:
            return "_Tabla no disponible._"
        sample = df.head(n).fillna("")
        columns = list(sample.columns)
        header = "| " + " | ".join(map(str, columns)) + " |"
        sep = "| " + " | ".join(["---"] * len(columns)) + " |"
        rows = [
            "| " + " | ".join(str(row[column]) for column in columns) + " |"
            for _, row in sample.iterrows()
        ]
        return "\n".join([header, sep, *rows])

    figure_lines = "\n".join(f"- outputs/figures/{name}" for name in [
        "golpes_por_jugador.png",
        "winner_error_jugador.png",
        "riesgo_efectividad.png",
        "clustering_jugadores.png",
        "errores_por_pareja.png",
        "metricas_globales_jugador.png",
        "golpes_por_partido.png",
        "error_winner_por_pareja.png",
    ])

    text = f"""# Actualizaciones sugeridas para la memoria

## Nuevos valores para resumen del dataset

{table_preview(dataset, 20)}

## Nuevas tablas de metricas

### Jugador-partido

{table_preview(player_metrics)}

### Pareja-partido

{table_preview(pair_metrics)}

### Perfiles de cluster

{table_preview(cluster_profiles)}

## Rutas de figuras

{figure_lines}

## Texto sugerido para `experimentacion.tex`

La experimentacion se plantea como una evaluacion offline sobre seis partidos reales procedentes de M3 Padel Academy. Para evitar sesgos por duplicidad, se utiliza la version `25_Madrid_Cuartos_chingalan_formato.csv` del partido de Madrid y se excluye la version alternativa indicada en el informe tecnico. El analisis combina metricas por jugador-partido, metricas por pareja-partido, agregados globales, clustering descriptivo a nivel jugador-partido y recomendaciones tacticas interpretables basadas en reglas.

El caso de estudio principal se mantiene en la final de Rotterdam 2025 entre Chingotto-Galan y Coello-Tapia, pero las conclusiones se contextualizan con el resto de partidos disponibles. El clustering se interpreta como herramienta descriptiva y no como prueba causal.

## Texto sugerido para `descripcion-informatica.tex`

El sistema se implementa como un pipeline reproducible en Python, ejecutable con `python scripts/run_pipeline.py`. El flujo lee la metadata de partidos, carga los CSV crudos con separador `;`, normaliza columnas, colapsa eventos, genera flags derivados, separa acciones analizables, calcula metricas, ejecuta clustering descriptivo y exporta tablas, figuras e informes. El recomendador no es un sistema en tiempo real: produce recomendaciones heuristicas e interpretables a partir de metricas agregadas.

## Texto sugerido para `conclusiones.tex`

La version actual amplia el alcance desde un unico caso de estudio a una evaluacion sobre seis partidos reales. Esto mejora la trazabilidad del sistema y permite comparar patrones entre partidos, aunque la muestra sigue siendo limitada y dependiente del etiquetado manual. Las recomendaciones deben entenderse como apoyo a la decision tactica del entrenador, no como sustituto del analisis tecnico experto.

## Advertencias para no sobreinterpretar

- Las metricas dependen de la calidad y consistencia del etiquetado manual.
- Los ratios con denominador cero se representan como NaN, no como rendimiento nulo.
- El clustering es descriptivo y sensible al numero reducido de observaciones jugador-partido.
- Las recomendaciones son reglas heuristicas basadas en evidencia agregada, no inferencia causal.
"""
    (config.REPORTS_DIR / "memoria_updates.md").write_text(text, encoding="utf-8")


def current_summary_from_outputs() -> dict[str, object]:
    dataset = read_csv_if_exists(config.TABLES_DIR / "dataset_summary.csv")
    summary_map = {}
    if not dataset.empty and {"metric", "value"}.issubset(dataset.columns):
        summary_map = dict(zip(dataset["metric"], dataset["value"]))
    return {
        "partidos_procesados": summary_map.get("csv_raw_leidos_ok", "pendiente"),
        "partidos_con_error": summary_map.get("csv_raw_con_error", "pendiente"),
        "filas_totales": summary_map.get("filas_limpias", "pendiente"),
        "acciones_analizables": summary_map.get("acciones_analizables", "pendiente"),
        "jugadores_distintos": summary_map.get("jugadores_distintos", "pendiente"),
        "parejas_distintas": summary_map.get("parejas_distintas", "pendiente"),
        "duplicados": summary_map.get("eventos_colapsados", "pendiente"),
    }


def write_technical_review(
    pipeline_summary: dict[str, object] | None = None,
    warnings: list[str] | None = None,
) -> None:
    pipeline_summary = pipeline_summary or {}
    warnings = warnings or []
    output_files = []
    for directory in [config.TABLES_DIR, config.REPORTS_DIR]:
        output_files.extend(
            str(path.relative_to(config.PROJECT_ROOT)) for path in directory.rglob("*") if path.is_file()
        )
    output_files.extend(
        str(path.relative_to(config.PROJECT_ROOT))
        for path in config.FIGURES_DIR.glob("*.png")
        if path.is_file()
    )
    output_files = sorted(output_files)
    generated = "\n".join(f"- `{path}`" for path in output_files) if output_files else "- Sin outputs generados."
    warning_text = "\n".join(f"- {item}" for item in warnings) if warnings else "- Sin warnings adicionales."

    text = f"""# Revision tecnica del repositorio

## Archivos creados o modificados

- Nuevo paquete reproducible en `src/tfg_padel/`.
- Nuevos scripts principales en `scripts/run_pipeline.py`, `scripts/validate_data.py`, `scripts/generate_figures.py`, `scripts/generate_tables.py` y `scripts/generate_recommendations.py`.
- Scripts antiguos movidos a `scripts/legacy/` porque dependian de interaccion manual, un unico partido o rutas intermedias.
- Modulos antiguos `src/data` y `src/common` movidos a `scripts/legacy/old_src/` tras refactorizar su logica util.
- Artefactos antiguos sueltos de `data/` movidos a `scripts/legacy/notes/` para separar datos reproducibles de notas previas.
- Parquets intermedios antiguos movidos a `scripts/legacy/old_interim/`; el nuevo pipeline escribe resultados finales en CSV.
- `requirements.txt`, `pyproject.toml`, `.gitignore`, `README.md`, `docs/data_dictionary.md` y anexos actualizados.
- `todo.txt` se transforma en trazabilidad dentro de este informe y deja de mantenerse como lista suelta. Sus ideas de analisis por juegos, saque/resto, breaks y visualizaciones temporales quedan como trabajo futuro, no como promesa implementada.

## Como ejecutar el proyecto

```bash
python scripts/run_pipeline.py
python scripts/validate_data.py
python scripts/generate_figures.py
python scripts/generate_tables.py
python scripts/generate_recommendations.py
```

## Resumen de ejecucion

- Partidos procesados: {pipeline_summary.get('partidos_procesados', 'pendiente')}
- Partidos con error: {pipeline_summary.get('partidos_con_error', 'pendiente')}
- Filas totales limpias: {pipeline_summary.get('filas_totales', 'pendiente')}
- Acciones analizables: {pipeline_summary.get('acciones_analizables', 'pendiente')}
- Jugadores distintos: {pipeline_summary.get('jugadores_distintos', 'pendiente')}
- Parejas distintas: {pipeline_summary.get('parejas_distintas', 'pendiente')}
- Eventos colapsados: {pipeline_summary.get('duplicados', 'pendiente')}

## Resultados generados

{generated}

## Limitaciones vigentes

- Los datos crudos no se versionan publicamente; el evaluador necesita colocar los CSV en `data/raw/`.
- Las fechas de partidos quedan como `pending_review` en metadata porque no se han verificado con fuente externa.
- Las recomendaciones son heuristicas y offline; no deben presentarse como sistema en tiempo real.
- El clustering usa pocas observaciones jugador-partido y debe interpretarse como apoyo descriptivo.
- La variable `Fuerza error` se interpreta como presion ejercida/errores forzados provocados si existe en el etiquetado.

## Puntos que debe mencionar la memoria

- La experimentacion principal usa seis partidos reales.
- El partido duplicado de Madrid queda excluido para no duplicar observaciones.
- Los NaN en ratios significan division no definida, no cero rendimiento.
- El caso de estudio principal es Rotterdam final Chingotto-Galan vs Coello-Tapia.

## Incoherencias detectadas entre memoria y codigo

- Si la memoria habla de un unico partido, debe actualizarse a evaluacion sobre seis partidos mas caso de estudio.
- Si la memoria habla de recomendador en tiempo real, debe corregirse a pipeline offline con reglas interpretables.
- Si la memoria presenta clustering global por jugador como analisis principal, debe cambiarse a clustering jugador-partido.

## Advertencias registradas

{warning_text}

## Riesgos de defensa

| Promesa de la memoria | Evidencia real del codigo | Riesgo | Correccion recomendada |
|---|---|---|---|
| Sistema de recomendacion deportiva | `src/tfg_padel/recommender.py` genera reglas heuristicas sobre CSV agregados | El tribunal puede esperar ML supervisado o tiempo real | Describirlo como apoyo offline a la decision tactica |
| Evaluacion robusta | Hay seis partidos, pero muestra limitada y etiquetado manual | Sobreinterpretar patrones como conclusiones generales | Hablar de evaluacion exploratoria multi-partido |
| Clustering de jugadores | `src/tfg_padel/clustering.py` clusteriza jugador-partido con scaler y k prudente | Confundir clusters con tipos universales de jugador | Presentar clusters como perfiles relativos a la muestra |
| Datos reales completos | `data/raw/` esta ignorado y depende del entorno local | Reproducibilidad externa incompleta sin datos | Documentar colocacion esperada de CSV y metadata |
| Calidad del dato suficiente | `outputs/reports/data_quality_report.md` registra ausencias y warnings | Que falten columnas o haya inconsistencias por CSV | Incluir limitaciones y warnings en la memoria |
"""
    (config.REPORTS_DIR / "technical_review.md").write_text(text, encoding="utf-8")
