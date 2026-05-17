# Diccionario de datos

Este documento resume las columnas detectadas y las variables derivadas usadas por el pipeline offline del TFG.

## Columnas originales detectadas

En los CSV locales se han detectado columnas M3 como:

- Identificacion temporal: `Row Name`, `Clip Start`, `Clip End`.
- Marcador: `Set_num`, `Set_P1`, `Set_P2`, `Juego_P1`, `Juego_P2`, `Punto_P1`, `Punto_P2`.
- Etiquetado de acción: `Jugador`, `Pareja`, `Servicio`, `Golpe_q`, `Cara_pala`, `Pared`.
- Resultado del punto o acción: `Winner`, `Error`, `Fuerza error`, `Punto_win`, `Punto_lost`, `Break_point`, `Break_fav`, `Break_con`, `Set_point`, `Set_win`, `Set_lost`, `Match point`.
- Zonas y coordenadas: `Zona saque`, `Zona resto`, `Inicio_gople: X`, `Inicio_gople: Y`, `Inicio_golpe: X`, `Inicio_golpe: Y`, `Fin_golpe: X`, `Fin_golpe: Y`.
- Columnas auxiliares de tiempo: sufijo `: Time`.

## Columnas normalizadas

El pipeline convierte nombres a `snake_case` sin tildes y coalesce alias frecuentes:

| Original | Normalizada | Uso |
|---|---|---|
| `Row Name` | `row_name` | clave de evento |
| `Clip Start` | `clip_start` | orden temporal |
| `Clip End` | `clip_end` | clave de evento |
| `Jugador` | `jugador` | agrupacion por jugador |
| `Pareja` | `pareja` | agrupacion por pareja |
| `Golpe_q` | `golpe_q` | filtro de acciones analizables |
| `Servicio` | `servicio` | flag de servicio |
| `Winner` | `winner` | flag de winner |
| `Error` | `error` | flags de error |
| `Fuerza error` | `fuerza_error` | presión/errores forzados provocados |
| `Inicio_gople: X`, `Inicio_golpe: X` | `inicio_x` | coordenada de inicio |
| `Fin_golpe: Y` | `fin_y` | coordenada de final |

## Variables de metadata

`data/metadata/matches_metadata.csv` contiene:

| Columna | Descripcion |
|---|---|
| `match_id` | identificador estable del partido |
| `file_name` | CSV crudo esperado en `data/raw/` |
| `tournament` | torneo indicado manualmente |
| `round` | ronda indicada manualmente |
| `date` | fecha, actualmente `pending_review` |
| `pair_1`, `pair_2` | parejas del partido |
| `notes` | notas metodologicas |

## Flags creados

| Flag | Definicion |
|---|---|
| `es_golpe` | `golpe_q` no vacio |
| `es_servicio` | `servicio` no vacio o `golpe_q` compatible con servicio/saque |
| `es_winner` | `winner` contiene etiqueta de winner |
| `es_error` | `error` no vacio, incluyendo `Error no forzado` y `Missed` |
| `es_error_no_forzado` | `error` contiene `Error no forzado` |
| `es_missed` | `error` contiene `Missed` |
| `es_fuerza_error` | `fuerza_error` no vacio |
| `es_punto_win` | `punto_win` no vacio |
| `es_punto_lost` | `punto_lost` no vacio |
| `es_break_point` | `break_point` no vacio |

## Metricas calculadas

### Jugador-partido

| Metrica | Formula | Escala |
|---|---|---|
| `total_golpes` | suma de `es_golpe` | conteo |
| `winners` | suma de `es_winner` | conteo |
| `errores_totales` | suma de `es_error` | conteo |
| `errores_no_forzados` | suma de `es_error_no_forzado` | conteo |
| `errores_forzados_provocados` | suma de `es_fuerza_error` | conteo |
| `servicios` | suma de `es_servicio` | conteo |
| `winner_pct` | `winners / total_golpes * 100` | porcentaje |
| `error_pct` | `errores_totales / total_golpes * 100` | porcentaje |
| `indice_riesgo` | `errores_no_forzados / errores_totales` | ratio 0-1 si definido |
| `efectividad_ofensiva` | `winners / errores_no_forzados` | ratio |
| `presion_ejercida_pct` | `errores_forzados_provocados / total_golpes * 100` | porcentaje |

### Pareja-partido

Se agregan los mismos conteos principales por `match_id`, `tournament`, `round` y `pareja`, excluyendo columnas especificas de jugador.

## Significado de NaN frente a 0

- `0` significa que el evento existe como posibilidad y se ha contado cero veces.
- `NaN` significa que una formula no esta definida, normalmente por denominador cero o dato no disponible.
- En ratios como `efectividad_ofensiva`, `NaN` no debe interpretarse como mala efectividad.

## Porcentajes

Los porcentajes se expresan en escala 0-100. Por ejemplo, `winner_pct = 12.5` significa 12.5 % de winners sobre golpes etiquetados del jugador o pareja.

## Advertencias sobre etiquetado manual

Las métricas dependen de la consistencia de las etiquetas del CSV. Si una columna falta en un partido, el pipeline registra warning y continúa cuando la métrica puede calcularse con las columnas disponibles. El informe de calidad detalla ausencias, formatos inconsistentes y divisiones por cero controladas.

## Salidas de recomendaciones

`outputs/tables/recommendations.csv` conserva la trazabilidad completa de cada recomendacion:

| Columna | Descripcion |
|---|---|
| `match_id` | partido al que pertenece la recomendacion |
| `scope` | nivel del objetivo: `player`, `pair`, `match` o equivalente |
| `target` | jugador, pareja o partido objetivo |
| `evidence_metric` | metrica que activa o justifica la regla |
| `evidence_value` | valor observado de la metrica de evidencia |
| `rule_applied` | regla heuristica aplicada |
| `recommendation` | recomendacion tactica generada |
| `justification` | explicacion cuantitativa de la recomendacion |
| `limitations` | limites interpretativos de la regla |

`outputs/tables/recommendations_summary.csv` resume la salida anterior con:

| Columna | Descripcion |
|---|---|
| `summary_type` | tipo de resumen: `total`, `by_match`, `by_rule`, `by_scope` |
| `category` | categoria concreta dentro del resumen |
| `count` | numero de recomendaciones |
| `share_pct` | porcentaje sobre el total de filas de recomendaciones |
| `notes` | aclaracion metodologica si aplica |

`outputs/tables/player_recommendation_cards.csv` consolida las recomendaciones de `scope == "player"` en una ficha por jugador y partido:

| Columna | Descripcion |
|---|---|
| `match_id` | partido de la ficha tactica |
| `match_label` | nombre legible del partido construido desde la metadata |
| `player` | jugador objetivo |
| `rules_triggered` | reglas activadas, separadas por `;` |
| `num_rules_triggered` | numero de reglas activadas para el jugador en el partido |
| `evidence_metrics` | métricas que justifican la ficha, separadas por `;` |
| `evidence_values` | valores asociados a las métricas de evidencia |
| `formatted_evidence` | evidencias presentadas con etiquetas legibles y valores redondeados a dos decimales |
| `player_profile` | perfil tactico interpretable asignado por reglas |
| `priority_label` | prioridad cualitativa: `Alta`, `Media`, `Baja` o `Sin evidencia` |
| `priority_reason` | justificacion textual de la prioridad asignada |
| `priority_score` | puntuacion auxiliar basada en numero de reglas y perfil |
| `tactical_diagnosis` | lectura tactica prudente del patron observado |
| `main_recommendation` | recomendacion principal consolidada |
| `secondary_recommendation` | recomendacion secundaria, si procede |
| `coach_note` | nota de uso para entrenador o analista |
| `limitations` | limitaciones agregadas sin duplicados |

Perfiles tacticos usados en las fichas:

| Perfil | Criterio resumido |
|---|---|
| `Atacante de alto riesgo` | se activan `high_winner_high_error` y `player_error_pct_above_match_mean` |
| `Finalizador eficiente` | se activa `high_offensive_efficiency_low_error` sin exceso de error relativo |
| `Constructor del punto` | se activa `high_volume_low_winner` sin senales simultaneas de alto riesgo ofensivo |
| `Foco potencial de presión` | se activa `player_error_pct_above_match_mean` sin `high_winner_high_error` |
| `Atacante agresivo` | se activa `high_winner_high_error` sin exceso de error relativo |
| `Perfil mixto ofensivo-constructor` | se activan `high_offensive_efficiency_low_error` y `high_volume_low_winner` |
| `Perfil mixto` | varias reglas activadas sin encaje limpio en perfiles anteriores |
| `Sin evidencia suficiente` | no hay reglas individuales suficientes |

El campo `formatted_evidence` transforma las evidencias técnicas en texto legible. Por ejemplo, `winner_pct_and_error_pct` con valores `8.2645;8.2645` se presenta como `Winner% = 8.26; Error% = 8.26`.

La prioridad de la ficha se interpreta de forma orientativa:

| Prioridad | Criterio |
|---|---|
| `Alta` | dos o más reglas activadas, perfil de atacante de alto riesgo o combinación de evidencia ofensiva y error elevado |
| `Media` | una regla individual con evidencia clara, como finalizador eficiente, foco potencial de presión o atacante agresivo |
| `Baja` | perfil contextual de construcción con una única regla `high_volume_low_winner` |
| `Sin evidencia` | reglas insuficientes para priorizar |

`outputs/tables/player_global_recommendation_summary.csv` agrega las fichas por jugador:

| Columna | Descripcion |
|---|---|
| `player` | jugador agregado |
| `matches_with_recommendations` | partidos en los que aparece con ficha |
| `total_cards` | numero de fichas jugador-partido |
| `total_rules_triggered` | suma de reglas activadas |
| `most_common_profile` | perfil tactico mas frecuente |
| `most_common_rules` | reglas mas frecuentes |
| `high_priority_cards` | fichas con prioridad `Alta` |
| `global_tactical_reading` | sintesis prudente del patron observado |
| `global_recommendation` | orientacion general basada en la muestra |
| `caution` | advertencia metodologica sobre muestra, contexto y caracter heuristico |

`outputs/tables/match_recommendation_summary.csv` resume la salida por partido:

| Columna | Descripcion |
|---|---|
| `match_id` | partido resumido |
| `match_label` | nombre legible del partido |
| `player_cards` | numero de fichas de jugador |
| `pair_recommendations` | recomendaciones de pareja en el partido |
| `high_priority_player_cards` | fichas individuales de prioridad alta |
| `main_player_profiles` | perfiles tacticos predominantes |
| `players_with_high_priority` | jugadores con ficha de prioridad alta |
| `summary_text` | lectura textual breve del partido |

## Salidas del recomendador clásico basado en contenido

`outputs/tables/classical_neighbors.csv` contiene los vecinos más similares de cada observación jugador-partido:

| Columna | Descripción |
|---|---|
| `target_match_id` | partido técnico de la observación objetivo |
| `target_match_label` | nombre legible del partido objetivo |
| `target_player` | jugador objetivo |
| `neighbor_rank` | posición del vecino dentro del top-k |
| `neighbor_match_id` | partido técnico del vecino |
| `neighbor_match_label` | nombre legible del partido vecino |
| `neighbor_player` | jugador vecino |
| `similarity` | similitud coseno entre vectores normalizados |
| `neighbor_profile` | perfil heurístico del vecino si existe ficha previa |
| `neighbor_main_recommendation` | recomendación principal del vecino si existe ficha previa |

`outputs/tables/classical_recommendations.csv` contiene la orientación generada por similitud:

| Columna | Descripción |
|---|---|
| `match_id` | partido técnico de la observación objetivo |
| `match_label` | nombre legible del partido |
| `player` | jugador objetivo |
| `recommended_profile` | perfil sugerido a partir de vecinos o fallback métrico |
| `recommended_action` | orientación táctica sugerida por similitud |
| `evidence` | justificación con similitud media y métricas usadas |
| `neighbors_used` | vecinos empleados y similitudes |
| `mean_similarity` | similitud media de los vecinos usados |
| `method` | método aplicado; valor esperado: `content_based_knn` |
| `limitations` | limitaciones metodológicas del baseline |

`outputs/tables/classical_recommender_diagnostics.csv` resume la ejecución:

| Columna | Descripción |
|---|---|
| `num_targets` | observaciones jugador-partido evaluadas |
| `num_recommendations` | recomendaciones clásicas generadas |
| `mean_similarity` | similitud media de los vecinos recuperados |
| `min_similarity` | similitud mínima observada |
| `max_similarity` | similitud máxima observada |
| `coverage_pct` | porcentaje de observaciones con salida generada |
| `players_covered` | jugadores cubiertos |
| `matches_covered` | partidos cubiertos |
| `k_neighbors` | número de vecinos usado |
| `overlap_with_heuristic_pct` | coincidencia exploratoria con el perfil heurístico cuando existe; no es accuracy |

Este recomendador no es colaborativo: no usa feedback explícito de usuarios ni validación con entrenadores. Debe interpretarse como baseline exploratorio basado en similitud de métricas jugador-partido, no como predicción de una acción óptima.

El informe explicativo `outputs/reports/classical_recommender_report.pdf` resume el método, las métricas utilizadas, los diagnósticos de similitud y las recomendaciones agrupadas por partido. Su finalidad es documentar el baseline de forma legible para la memoria, manteniendo la salida tabular como fuente trazable.

Las versiones LaTeX se generan en `outputs/reports/tables_latex/`: `recommendations_summary.tex`, `player_recommendation_examples.tex` y `global_player_summary.tex`. Los informes legibles en PDF se generan en `outputs/reports/recommendations_report.pdf` y `outputs/reports/player_recommendation_cards.pdf`.

Las recomendaciones se generan mediante reglas heurísticas sobre métricas agregadas. No son predicciones automáticas de la mejor jugada y no sustituyen al entrenador.
