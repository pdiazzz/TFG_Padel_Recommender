# Diccionario de datos

Este documento resume las columnas detectadas y las variables derivadas usadas por el pipeline offline del TFG.

## Columnas originales detectadas

En los CSV locales se han detectado columnas M3 como:

- Identificacion temporal: `Row Name`, `Clip Start`, `Clip End`.
- Marcador: `Set_num`, `Set_P1`, `Set_P2`, `Juego_P1`, `Juego_P2`, `Punto_P1`, `Punto_P2`.
- Etiquetado de accion: `Jugador`, `Pareja`, `Servicio`, `Golpe_q`, `Cara_pala`, `Pared`.
- Resultado del punto o accion: `Winner`, `Error`, `Fuerza error`, `Punto_win`, `Punto_lost`, `Break_point`, `Break_fav`, `Break_con`, `Set_point`, `Set_win`, `Set_lost`, `Match point`.
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
| `Fuerza error` | `fuerza_error` | presion/errores forzados provocados |
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

Las metricas dependen de la consistencia de las etiquetas del CSV. Si una columna falta en un partido, el pipeline registra warning y continua cuando la metrica puede calcularse con las columnas disponibles. El informe de calidad detalla ausencias, formatos inconsistentes y divisiones por cero controladas.

