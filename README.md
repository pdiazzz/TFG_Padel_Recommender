# Sistema de Recomendación Deportiva en Pádel

Trabajo de Fin de Grado orientado a un pipeline offline de análisis deportivo y generación de recomendaciones tácticas interpretables para partidos de pádel.

El proyecto trabaja con CSV etiquetados procedentes de M3 Pádel Academy. El objetivo no es construir un recomendador en tiempo real, sino una herramienta reproducible de ingesta, limpieza, análisis exploratorio, métricas derivadas, perfilado descriptivo y apoyo táctico basado en reglas.

## Objetivo

Preparar un flujo reproducible que permita:

- cargar varios partidos reales desde `data/raw/`;
- normalizar y limpiar columnas heterogéneas;
- calcular métricas por jugador-partido y pareja-partido;
- generar clustering descriptivo a nivel jugador-partido;
- exportar tablas, figuras e informes para la memoria;
- producir recomendaciones tácticas justificadas por métricas.

## Alcance

La experimentacion principal usa diez partidos reales declarados en `data/metadata/matches_metadata.csv`. La version alternativa `25_Madrid_Cuartos_chingalan CSV.csv` queda excluida para evitar duplicar observaciones del partido de Madrid.

Las recomendaciones son apoyo a la decisión técnica del entrenador. No sustituyen el análisis experto ni incorporan vídeo, marcador contextual avanzado, estado físico o instrucciones tácticas previas.

## Estructura

```text
data/
  raw/                 # CSV crudos locales, no versionados
  metadata/            # metadata reproducible de partidos
  processed/           # datasets limpios generados
outputs/
  tables/              # tablas CSV para memoria
  figures/             # figuras PNG
  reports/             # informes tecnicos y anexos auxiliares
scripts/
  run_pipeline.py
  validate_data.py
  generate_figures.py
  generate_tables.py
  generate_recommendations.py
  generate_match_dashboards.py
  legacy/              # scripts antiguos conservados como trazabilidad
src/
  tfg_padel/           # paquete principal del pipeline
notebooks/
  exploration/         # notebooks exploratorios, no necesarios para reproducir outputs
docs/
  data_dictionary.md
anexos/
  repositorio-ejecucion.tex
  diccionario-datos.tex
```

## Instalación

Requisitos: Python 3.10 o superior.

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Datos de entrada esperados

Los CSV crudos deben colocarse en `data/raw/`. El lector usa `;` como separador esperado y aplica fallback para CSV UTF-16 separados por coma. La metadata define los diez partidos usados:

- `25_Roterdam_Final_Chingalan_CoelloTapia CSV.csv`
- `25_Milan_Semifinal_Chingalan_DinnenoAusburguer CSV.csv`
- `25_Roterdam_Semifinal_Chingalan_LebronStupa CSV.csv`
- `25_Roterdam_CoelloTapia_NietoYanguas CSV.csv`
- `25_Madrid_Cuartos_chingalan_formato.csv`
- `Milan_Final_Chingalan_CoelloTapia CSV.csv`
- `25_Barcelona_Cuartos_ChinGalan_MomoGuerrero CSV.csv`
- `25_Barcelona_Cuartos_CoelloTapia_BergaminiLeal CSV.csv`
- `25_Barcelona_Final_ChinGalan_CoelloTapia CSV.csv`
- `25_Barcelona_Semis_ChinGalan_NavarroSanz.csv`

## Ejecución

Comando principal:

```bash
python scripts/run_pipeline.py
```

Comandos auxiliares reproducibles:

```bash
python scripts/validate_data.py
python scripts/generate_figures.py
python scripts/generate_tables.py
python scripts/generate_recommendations.py
python scripts/generate_recommendations_report.py
python scripts/generate_classical_recommendations.py
python scripts/generate_match_dashboards.py
```

## Outputs principales

- `data/processed/matches_clean.csv`
- `data/processed/actions_clean.csv`
- `data/processed/player_match_metrics.csv`
- `data/processed/pair_match_metrics.csv`
- `outputs/tables/dataset_summary.csv`
- `outputs/tables/data_quality_summary.csv`
- `outputs/tables/player_global_metrics.csv`
- `outputs/tables/pair_global_metrics.csv`
- `outputs/tables/clustering_scores.csv`
- `outputs/tables/player_match_clusters.csv`
- `outputs/tables/cluster_profiles.csv`
- `outputs/tables/recommendations.csv`
- `outputs/tables/recommendations_summary.csv`
- `outputs/tables/player_recommendation_cards.csv`
- `outputs/tables/player_global_recommendation_summary.csv`
- `outputs/tables/match_recommendation_summary.csv`
- `outputs/tables/classical_recommendations.csv`
- `outputs/tables/classical_neighbors.csv`
- `outputs/tables/classical_recommender_diagnostics.csv`
- `outputs/figures/*.png`
- `outputs/figures/match_dashboards/dashboard_<match_id>.png`
- `outputs/reports/data_quality_report.md`
- `outputs/reports/technical_review.md`
- `outputs/reports/memoria_updates.md`
- `outputs/reports/recommendations_report.pdf`
- `outputs/reports/player_recommendation_cards.pdf`
- `outputs/reports/classical_recommender_summary.md`
- `outputs/reports/classical_recommender_report.pdf`
- `outputs/reports/memory_update_classical_recommender.md`
- `outputs/tables/match_dashboard_summary.csv`

## Recomendaciones

El recomendador aplica reglas interpretables sobre métricas agregadas. Por ejemplo, si un jugador tiene `error_pct` superior a la media del partido, se propone aumentar presión o volumen de juego sobre ese jugador con cautela contextual. Cada recomendación se exporta con métrica de evidencia, regla aplicada, justificación y limitaciones.

### Generación de informes de recomendaciones

Para generar la salida trazable por regla, las fichas tácticas consolidadas y los informes PDF:

```bash
python scripts/generate_recommendations.py
python scripts/generate_recommendations_report.py
```

El primer comando actualiza `outputs/tables/recommendations.csv`, que conserva una fila por regla activada y mantiene la trazabilidad tecnica de `match_id`, `scope`, `target`, metrica de evidencia, regla, justificacion y limitaciones.

El segundo comando genera:

- `outputs/tables/recommendations_summary.csv`
- `outputs/tables/player_recommendation_cards.csv`
- `outputs/tables/player_global_recommendation_summary.csv`
- `outputs/tables/match_recommendation_summary.csv`
- `outputs/reports/recommendations_report.pdf`
- `outputs/reports/player_recommendation_cards.pdf`
- `outputs/reports/tables_latex/recommendations_summary.tex`
- `outputs/reports/tables_latex/player_recommendation_examples.tex`
- `outputs/reports/tables_latex/global_player_summary.tex`

Las fichas tácticas consolidan las reglas activadas por jugador y partido en perfiles interpretables como `Atacante de alto riesgo`, `Finalizador eficiente`, `Constructor del punto`, `Foco potencial de presión` o `Perfil mixto ofensivo-constructor`. Incluyen `match_label` para mostrar nombres legibles de partido, `formatted_evidence` para presentar las evidencias con etiquetas claras y `priority_reason` para justificar la prioridad asignada.

Los informes PDF se generan con fuente compatible con UTF-8 y texto académico en español. Las tablas LaTeX de `outputs/reports/tables_latex/` están preparadas para incorporarse a la memoria, usando `tabularx`. Estas salidas siguen siendo recomendaciones tácticas heurísticas e interpretables basadas en métricas: no son predicciones automáticas de la mejor acción ni sustituyen al entrenador.

### Recomendador clásico basado en contenido

Como baseline exploratorio complementario, el proyecto incluye un recomendador clásico tipo kNN basado en contenido a nivel jugador-partido. Cada observación se representa mediante métricas agregadas como `winner_pct`, `error_pct`, `indice_riesgo`, `efectividad_ofensiva`, `presion_ejercida_pct` y `total_golpes`; las variables se normalizan con `StandardScaler` y se comparan mediante similitud coseno.

Ejecución:

```bash
python scripts/generate_classical_recommendations.py
```

Outputs:

- `outputs/tables/classical_recommendations.csv`
- `outputs/tables/classical_neighbors.csv`
- `outputs/tables/classical_recommender_diagnostics.csv`
- `outputs/reports/classical_recommender_summary.md`
- `outputs/reports/classical_recommender_report.pdf`
- `outputs/reports/memory_update_classical_recommender.md`

El PDF `classical_recommender_report.pdf` explica el criterio de generación, las métricas usadas, los vecinos recuperados y la orientación sugerida para cada jugador-partido. Este baseline usa, cuando existen, las fichas tácticas heurísticas previas de `player_recommendation_cards.csv` para inferir perfiles y orientaciones desde vecinos similares. No utiliza feedback explícito, no está validado con entrenadores y no debe interpretarse como recomendador autónomo ni como predicción de una acción óptima.

## Limitaciones

- Muestra todavia reducida: diez partidos reales.
- Dependencia del etiquetado manual de eventos.
- Los datos crudos no se versionan públicamente.
- Las fechas quedan como `pending_review` hasta verificación externa.
- El clustering es descriptivo y no causal.
- Los valores `NaN` en ratios indican division no definida, no valor cero.
