from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pandas as pd

from . import config


def load_matches_metadata(path: Path | None = None) -> pd.DataFrame:
    path = path or config.MATCHES_METADATA_PATH
    if not path.exists():
        raise FileNotFoundError(f"No existe metadata de partidos: {path}")

    metadata = pd.read_csv(path, dtype="string")
    columns = list(metadata.columns)
    if columns != config.METADATA_COLUMNS:
        raise ValueError(
            "matches_metadata.csv debe tener exactamente estas columnas: "
            + ", ".join(config.METADATA_COLUMNS)
        )

    duplicated = metadata["match_id"].duplicated()
    if duplicated.any():
        values = metadata.loc[duplicated, "match_id"].tolist()
        raise ValueError(f"match_id duplicado en metadata: {values}")

    return metadata


def sniff_separator(path: Path, encoding: str) -> str | None:
    with path.open("r", encoding=encoding, errors="ignore", newline="") as handle:
        sample = handle.read(4096)
    try:
        return csv.Sniffer().sniff(sample, delimiters=";,|\t").delimiter
    except csv.Error:
        return None


def read_csv_with_fallback(path: Path, expected_sep: str = config.RAW_SEPARATOR) -> tuple[pd.DataFrame, list[str], dict[str, Any]]:
    warnings: list[str] = []
    encodings = ["utf-8-sig", "utf-8", "latin1", "utf-16"]
    separators = [expected_sep]
    last_error: Exception | None = None

    for encoding in encodings:
        for sep in separators:
            try:
                df = pd.read_csv(path, sep=sep, encoding=encoding, on_bad_lines="warn", low_memory=False)
                if df.shape[1] <= 1:
                    detected = sniff_separator(path, encoding)
                    if detected and detected != sep:
                        warnings.append(
                            f"{path.name}: separador '{sep}' produjo una sola columna; se intenta '{detected}'."
                        )
                        df = pd.read_csv(
                            path,
                            sep=detected,
                            encoding=encoding,
                            on_bad_lines="warn",
                            low_memory=False,
                        )
                        sep = detected
                    elif expected_sep != ",":
                        warnings.append(
                            f"{path.name}: lectura con separador '{sep}' produjo una sola columna."
                        )
                info = {"encoding": encoding, "separator": sep, "rows": len(df), "columns": len(df.columns)}
                return df, warnings, info
            except Exception as exc:  # pandas raises several parser/codec exceptions here
                last_error = exc
                continue

    raise RuntimeError(f"No se pudo leer {path.name}: {last_error}")


def attach_metadata(df: pd.DataFrame, metadata_row: pd.Series) -> pd.DataFrame:
    out = df.copy()
    for column in config.METADATA_COLUMNS:
        if column == "file_name":
            out["file_name"] = metadata_row[column]
            out["source_file"] = metadata_row[column]
        else:
            out[column] = metadata_row[column]
    return out


def load_raw_matches(metadata: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    frames: list[pd.DataFrame] = []
    report_rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    for _, row in metadata.iterrows():
        file_name = str(row["file_name"])
        path = config.RAW_DIR / file_name
        base_report: dict[str, Any] = {
            "match_id": row["match_id"],
            "file_name": file_name,
            "status": "ok",
            "rows": 0,
            "columns": 0,
            "encoding": "",
            "separator": "",
            "warning": "",
        }

        if not path.exists():
            message = f"No existe el CSV declarado en metadata: {file_name}"
            warnings.append(message)
            base_report.update({"status": "error", "warning": message})
            report_rows.append(base_report)
            continue

        try:
            raw_df, read_warnings, info = read_csv_with_fallback(path)
            raw_df = attach_metadata(raw_df, row)
            raw_df["raw_row_number"] = range(1, len(raw_df) + 1)
            frames.append(raw_df)
            warnings.extend(read_warnings)
            base_report.update(
                {
                    "rows": info["rows"],
                    "columns": info["columns"],
                    "encoding": info["encoding"],
                    "separator": info["separator"],
                    "warning": " | ".join(read_warnings),
                }
            )
            report_rows.append(base_report)
        except Exception as exc:
            message = f"Error leyendo {file_name}: {exc}"
            warnings.append(message)
            base_report.update({"status": "error", "warning": message})
            report_rows.append(base_report)

    if frames:
        raw = pd.concat(frames, ignore_index=True, sort=False)
    else:
        raw = pd.DataFrame()

    return raw, pd.DataFrame(report_rows), warnings


def write_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = df.to_csv(index=False, lineterminator="\n")
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8").replace("\r\n", "\n")
            if existing == content:
                return
        except OSError:
            pass
    try:
        path.write_text(content, encoding="utf-8")
    except PermissionError as exc:
        raise PermissionError(
            f"No se pudo escribir {path}. Cierra el archivo si está abierto en Excel, "
            "LibreOffice u otro visor y vuelve a ejecutar el comando."
        ) from exc


def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, low_memory=False)
    return pd.DataFrame()
