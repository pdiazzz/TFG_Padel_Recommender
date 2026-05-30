# Sistema de soporte a la decisión para el análisis táctico de partidos de pádel

Trabajo de Fin de Grado orientado a un pipeline offline de ciencia de datos para analizar partidos de pádel ya registrados y generar apoyo cuantitativo para entrenadores o analistas.

El proyecto trabaja con ficheros CSV etiquetados procedentes de M3 Pádel Academy. El objetivo principal no es construir un sistema autónomo que decida la táctica, sino una herramienta reproducible para ingerir datos, limpiarlos, transformarlos en acciones analizables, calcular métricas, comparar actuaciones y producir tablas, figuras, dashboards e informes útiles para el análisis posterior al partido.

## Contenido Del Repositorio

El repositorio público contiene el código y la documentación necesarios para reproducir el pipeline, pero no incluye los datos crudos reales ni los resultados generados a partir de ellos.

```text
src/tfg_padel/        # paquete principal del pipeline
scripts/              # scripts de ejecución reproducible
data/metadata/        # metadata de los partidos esperados
docs/                 # documentación auxiliar
anexos/               # anexos técnicos de la memoria
tables/resultados/    # tablas LaTeX concretas usadas en la memoria
```

Los directorios `data/raw/`, `data/processed/` y `outputs/` se generan o completan localmente durante la ejecución y no forman parte del repositorio público.

## Objetivo

Preparar un flujo reproducible que permita:

- cargar partidos reales desde `data/raw/`;
- normalizar y limpiar columnas heterogéneas;
- transformar eventos etiquetados en acciones analizables;
- calcular métricas por jugador-partido, pareja-partido y agregados globales;
- comparar actuaciones de jugadores, parejas y partidos;
- generar clustering descriptivo a nivel jugador-partido;
- exportar tablas, figuras, dashboards e informes;
- producir orientaciones tácticas revisables, justificadas por métricas.

## Alcance

La experimentación principal usa diez partidos reales declarados en `data/metadata/matches_metadata.csv`. La versión alternativa `25_Madrid_Cuartos_chingalan CSV.csv` queda excluida para evitar duplicar observaciones del partido de Madrid.

El sistema procesa partidos ya registrados. No es una aplicación en tiempo real, no predice resultados y no decide automáticamente la mejor táctica. Las orientaciones generadas son hipótesis de apoyo al análisis técnico y deben contrastarse con vídeo, marcador contextual, estado físico, instrucciones previas y criterio experto.

## Datos

Los datos crudos no se incluyen en este repositorio por restricciones de privacidad y confidencialidad. Para ejecutar el pipeline, los CSV deben colocarse localmente en `data/raw/` con los nombres definidos en `data/metadata/matches_metadata.csv`.

El lector usa `;` como separador esperado y aplica un fallback para CSV UTF-16 separados por coma. Los ficheros esperados son:

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

## Instalación

Requisitos: Python 3.10 o superior.

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

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

## Salidas Generadas

Tras la ejecución se generan datasets procesados y artefactos de análisis, principalmente:

- `data/processed/matches_clean.csv`
- `data/processed/actions_clean.csv`
- `data/processed/player_match_metrics.csv`
- `data/processed/pair_match_metrics.csv`
- `outputs/tables/*.csv`
- `outputs/figures/*.png`
- `outputs/figures/match_dashboards/*.png`
- `outputs/reports/*.md`
- `outputs/reports/*.pdf`
- `outputs/reports/tables_latex/*.tex`

Estas salidas no se versionan en el repositorio público porque derivan de datos reales no incluidos.

## Funcionalidades Analíticas

El pipeline carga la metadata de partidos, lee los CSV crudos, normaliza nombres de columnas, colapsa eventos redundantes, crea flags derivados y separa las acciones analizables. A partir de esas acciones calcula métricas de volumen, winners, errores, riesgo, efectividad ofensiva y presión ejercida, según el nivel de agregación disponible.

Las salidas permiten revisar el rendimiento por jugador y pareja, comparar actuaciones entre partidos, analizar perfiles relativos mediante clustering jugador-partido y consultar dashboards individuales por encuentro. Estas visualizaciones y tablas están pensadas como apoyo para la memoria y para una revisión técnica posterior, no como sustituto del análisis experto.

## Orientaciones Tácticas

El sistema incluye un módulo de reglas heurísticas que transforma determinadas evidencias métricas en orientaciones tácticas revisables. Por ejemplo, si un jugador presenta `error_pct` por encima de la media del partido, se documenta una posible línea de presión sobre ese jugador con cautela contextual.

Cada fila conserva `match_id`, nivel de análisis, objetivo, métrica de evidencia, valor observado, regla aplicada, orientación, justificación y limitaciones. Las fichas consolidadas resumen estas reglas en perfiles interpretables como `Atacante de alto riesgo`, `Finalizador eficiente`, `Constructor del punto`, `Foco potencial de presión` o `Perfil mixto ofensivo-constructor`.

## Línea Base Basada En Contenido

Como funcionalidad secundaria, el proyecto incorpora una línea base basada en contenido a nivel jugador-partido. Cada observación se representa mediante métricas agregadas como `winner_pct`, `error_pct`, `indice_riesgo`, `efectividad_ofensiva`, `presion_ejercida_pct` y `total_golpes`; las variables se normalizan con `StandardScaler` y se comparan mediante similitud coseno.

Esta línea base recupera actuaciones jugador-partido parecidas y usa, cuando existen, fichas tácticas previas para proponer una orientación por similitud. No utiliza feedback explícito, no está validada con entrenadores y no debe interpretarse como evaluación definitiva ni como decisión táctica autónoma.

## Limitaciones

- Muestra reducida: diez partidos reales.
- Dependencia del etiquetado manual de eventos.
- Datos crudos no incluidos por privacidad/confidencialidad.
- Fechas marcadas como `pending_review` hasta verificación externa.
- Clustering descriptivo y no causal.
- Valores `NaN` en ratios interpretados como división no definida, no como valor cero.
- Orientaciones tácticas entendidas como apoyo cuantitativo revisable, no como demostración directa de mejora competitiva.
