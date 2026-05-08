from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
METADATA_DIR = DATA_DIR / "metadata"
PROCESSED_DIR = DATA_DIR / "processed"

OUTPUTS_DIR = PROJECT_ROOT / "outputs"
TABLES_DIR = OUTPUTS_DIR / "tables"
FIGURES_DIR = OUTPUTS_DIR / "figures"
REPORTS_DIR = OUTPUTS_DIR / "reports"
LATEX_TABLES_DIR = REPORTS_DIR / "tables_latex"

DOCS_DIR = PROJECT_ROOT / "docs"
ANEXOS_DIR = PROJECT_ROOT / "anexos"

MATCHES_METADATA_PATH = METADATA_DIR / "matches_metadata.csv"

RAW_SEPARATOR = ";"
RANDOM_STATE = 42

METADATA_COLUMNS = [
    "match_id",
    "file_name",
    "tournament",
    "round",
    "date",
    "pair_1",
    "pair_2",
    "notes",
]

MAIN_MATCH_FILES = [
    "25_Roterdam_Final_Chingalan_CoelloTapia CSV.csv",
    "25_Milan_Semifinal_Chingalan_DinnenoAusburguer CSV.csv",
    "25_Roterdam_Semifinal_Chingalan_LebronStupa CSV.csv",
    "25_Roterdam_CoelloTapia_NietoYanguas CSV.csv",
    "25_Madrid_Cuartos_chingalan_formato.csv",
    "Milan_Final_Chingalan_CoelloTapia CSV.csv",
]

EXCLUDED_RAW_FILES = [
    "25_Madrid_Cuartos_chingalan CSV.csv",
]

EXPECTED_NORMALIZED_COLUMNS = [
    "row_name",
    "clip_start",
    "clip_end",
    "jugador",
    "pareja",
    "golpe_q",
    "servicio",
    "winner",
    "error",
    "fuerza_error",
    "punto_win",
    "punto_lost",
    "break_point",
]

CRITICAL_ANALYSIS_COLUMNS = [
    "match_id",
    "jugador",
    "pareja",
    "golpe_q",
    "winner",
    "error",
    "fuerza_error",
]

PLAYER_METRIC_COLUMNS = [
    "match_id",
    "tournament",
    "round",
    "jugador",
    "pareja",
    "total_golpes",
    "winners",
    "errores_totales",
    "errores_no_forzados",
    "errores_forzados_provocados",
    "servicios",
    "winner_pct",
    "error_pct",
    "indice_riesgo",
    "efectividad_ofensiva",
    "presion_ejercida_pct",
]

PAIR_METRIC_COLUMNS = [
    "match_id",
    "tournament",
    "round",
    "pareja",
    "total_golpes",
    "winners",
    "errores_totales",
    "errores_no_forzados",
    "winner_pct",
    "error_pct",
    "presion_ejercida_pct",
]

CLUSTER_FEATURE_COLUMNS = [
    "winner_pct",
    "error_pct",
    "indice_riesgo",
    "efectividad_ofensiva",
    "presion_ejercida_pct",
]

RECOMMENDATION_COLUMNS = [
    "match_id",
    "scope",
    "target",
    "evidence_metric",
    "evidence_value",
    "rule_applied",
    "recommendation",
    "justification",
    "limitations",
]


def ensure_directories() -> None:
    """Create every directory used by the reproducible pipeline."""
    for path in [
        RAW_DIR,
        METADATA_DIR,
        PROCESSED_DIR,
        TABLES_DIR,
        FIGURES_DIR,
        REPORTS_DIR,
        LATEX_TABLES_DIR,
        DOCS_DIR,
        ANEXOS_DIR,
        PROJECT_ROOT / "notebooks" / "exploration",
    ]:
        path.mkdir(parents=True, exist_ok=True)

