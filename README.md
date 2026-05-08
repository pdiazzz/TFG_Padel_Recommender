# Sistema de Recomendacion Deportiva en Padel

Trabajo de Fin de Grado orientado a un pipeline offline de analisis deportivo y generacion de recomendaciones tacticas interpretables para partidos de padel.

El proyecto trabaja con CSV etiquetados procedentes de M3 Padel Academy. El objetivo no es construir un recomendador en tiempo real, sino una herramienta reproducible de ingesta, limpieza, analisis exploratorio, metricas derivadas, perfilado descriptivo y apoyo tactico basado en reglas.

## Objetivo

Preparar un flujo reproducible que permita:

- cargar varios partidos reales desde `data/raw/`;
- normalizar y limpiar columnas heterogeneas;
- calcular metricas por jugador-partido y pareja-partido;
- generar clustering descriptivo a nivel jugador-partido;
- exportar tablas, figuras e informes para la memoria;
- producir recomendaciones tacticas justificadas por metricas.

## Alcance

La experimentacion principal usa seis partidos reales declarados en `data/metadata/matches_metadata.csv`. La version alternativa `25_Madrid_Cuartos_chingalan CSV.csv` queda excluida para evitar duplicar observaciones del partido de Madrid.

Las recomendaciones son apoyo a la decision tecnica del entrenador. No sustituyen el analisis experto ni incorporan video, marcador contextual avanzado, estado fisico o instrucciones tacticas previas.

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

## Instalacion

Requisitos: Python 3.10 o superior.

```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Datos de entrada esperados

Los CSV crudos deben colocarse en `data/raw/` y leerse con separador `;`. La metadata define los seis partidos usados:

- `25_Roterdam_Final_Chingalan_CoelloTapia CSV.csv`
- `25_Milan_Semifinal_Chingalan_DinnenoAusburguer CSV.csv`
- `25_Roterdam_Semifinal_Chingalan_LebronStupa CSV.csv`
- `25_Roterdam_CoelloTapia_NietoYanguas CSV.csv`
- `25_Madrid_Cuartos_chingalan_formato.csv`
- `Milan_Final_Chingalan_CoelloTapia CSV.csv`

## Ejecucion

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
- `outputs/figures/*.png`
- `outputs/reports/data_quality_report.md`
- `outputs/reports/technical_review.md`
- `outputs/reports/memoria_updates.md`

## Recomendaciones

El recomendador aplica reglas interpretables sobre metricas agregadas. Por ejemplo, si un jugador tiene `error_pct` superior a la media del partido, se propone aumentar presion o volumen de juego sobre ese jugador con cautela contextual. Cada recomendacion se exporta con metrica de evidencia, regla aplicada, justificacion y limitaciones.

## Limitaciones

- Muestra reducida: seis partidos reales.
- Dependencia del etiquetado manual de eventos.
- Los datos crudos no se versionan publicamente.
- Las fechas quedan como `pending_review` hasta verificacion externa.
- El clustering es descriptivo y no causal.
- Los valores `NaN` en ratios indican division no definida, no valor cero.

