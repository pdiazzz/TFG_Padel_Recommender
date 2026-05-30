# Sistema de soporte a la decisión para el análisis táctico de partidos de pádel

Trabajo de Fin de Grado orientado a un pipeline offline de ciencia de datos para analizar partidos de pádel ya registrados y generar apoyo cuantitativo para entrenadores o analistas.

El proyecto trabaja con CSV etiquetados procedentes de M3 Pádel Academy. Su objetivo principal es construir una herramienta reproducible para ingerir datos, limpiarlos, transformarlos en acciones analizables, calcular métricas, comparar actuaciones y producir tablas, figuras, dashboards e informes útiles para el análisis posterior al partido.

## Objetivo

Preparar un flujo reproducible que permita:

- cargar partidos reales desde `data/raw/`;
- normalizar y limpiar columnas heterogéneas;
- transformar eventos etiquetados en acciones analizables;
- calcular métricas por jugador-partido, pareja-partido y agregados globales;
- comparar actuaciones de jugadores, parejas y partidos;
- generar clustering descriptivo a nivel jugador-partido;
- exportar tablas, figuras, dashboards e informes para la memoria;
- producir orientaciones tácticas revisables, justificadas por métricas.

## Alcance

La experimentación principal usa diez partidos reales declarados en `data/metadata/matches_metadata.csv`. La versión alternativa `25_Madrid_Cuartos_chingalan CSV.csv` queda excluida para evitar duplicar observaciones del partido de Madrid.

El sistema procesa partidos ya registrados. No es una aplicación en tiempo real, no predice resultados y no decide automáticamente la mejor táctica. Las orientaciones generadas son hipótesis de apoyo al análisis técnico y deben contrastarse con vídeo, marcador contextual, estado físico, instrucciones previas y criterio experto.

## Estructura

```text
data/
  raw/                 # CSV crudos locales, no versionados
  metadata/            # metadata reproducible de partidos
  processed/           # datasets limpios generados
outputs/
  tables/              # tablas CSV para memoria
  figures/             # figuras PNG y dashboards por partido
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

## Funcionalidades analíticas

El pipeline carga la metadata de partidos, lee los CSV crudos, normaliza nombres de columnas, colapsa eventos redundantes, crea flags derivados y separa las acciones analizables. A partir de esas acciones calcula métricas de volumen, winners, errores, riesgo, efectividad ofensiva y presión ejercida, según el nivel de agregación disponible.

Las salidas permiten revisar el rendimiento por jugador y pareja, comparar actuaciones entre partidos, analizar perfiles relativos mediante clustering jugador-partido y consultar dashboards individuales por encuentro. Estas visualizaciones y tablas están pensadas como apoyo para la memoria y para una revisión técnica posterior, no como sustituto del análisis experto.

## Orientaciones tácticas

El sistema incluye un módulo de reglas heurísticas que transforma determinadas evidencias métricas en orientaciones tácticas revisables. Por ejemplo, si un jugador presenta `error_pct` por encima de la media del partido, se documenta una posible línea de presión sobre ese jugador con cautela contextual. Cada fila conserva `match_id`, nivel de análisis, objetivo, métrica de evidencia, valor observado, regla aplicada, orientación, justificación y limitaciones.

Para actualizar estas salidas:

```bash
python scripts/generate_recommendations.py
python scripts/generate_recommendations_report.py
```

El primer comando actualiza `outputs/tables/recommendations.csv` y `outputs/tables/latex_recommendations.csv`. El segundo genera tablas de resumen, fichas tácticas por jugador-partido e informes PDF:

- `outputs/tables/recommendations_summary.csv`
- `outputs/tables/player_recommendation_cards.csv`
- `outputs/tables/player_global_recommendation_summary.csv`
- `outputs/tables/match_recommendation_summary.csv`
- `outputs/reports/recommendations_report.pdf`
- `outputs/reports/player_recommendation_cards.pdf`
- `outputs/reports/tables_latex/recommendations_summary.tex`
- `outputs/reports/tables_latex/player_recommendation_examples.tex`
- `outputs/reports/tables_latex/global_player_summary.tex`

Las fichas consolidan reglas activadas por jugador y partido en perfiles interpretables como `Atacante de alto riesgo`, `Finalizador eficiente`, `Constructor del punto`, `Foco potencial de presión` o `Perfil mixto ofensivo-constructor`. Incluyen evidencias formateadas, prioridad y una nota metodológica para evitar sobreinterpretaciones.

## Línea base basada en contenido

Como funcionalidad secundaria, el proyecto incorpora una línea base basada en contenido a nivel jugador-partido. Cada observación se representa mediante métricas agregadas como `winner_pct`, `error_pct`, `indice_riesgo`, `efectividad_ofensiva`, `presion_ejercida_pct` y `total_golpes`; las variables se normalizan con `StandardScaler` y se comparan mediante similitud coseno.

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

Esta línea base recupera actuaciones jugador-partido parecidas y usa, cuando existen, fichas tácticas previas para proponer una orientación por similitud. No utiliza feedback explícito, no está validada con entrenadores y no debe interpretarse como evaluación definitiva ni como decisión táctica autónoma.

## Limitaciones

- Muestra todavía reducida: diez partidos reales.
- Dependencia del etiquetado manual de eventos.
- Los datos crudos no se versionan públicamente.
- Las fechas quedan como `pending_review` hasta verificación externa.
- El clustering es descriptivo y no causal.
- Los valores `NaN` en ratios indican división no definida, no valor cero.
- Las orientaciones tácticas son apoyo cuantitativo revisable; no demuestran mejora competitiva por sí mismas.
