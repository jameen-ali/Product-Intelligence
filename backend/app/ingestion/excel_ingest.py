"""
Excel / CSV Catalog Ingestion Service.
Supports: .csv, .xlsx, .xlsm (and optionally .xls)
Produces structured records with per-cell sheet/row/column provenance.
No LLM calls — fully deterministic column-to-attribute mapping.
"""
import logging
import re
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical attribute mapping — covers all common industrial column variants
# ---------------------------------------------------------------------------
COLUMN_MAPPING: Dict[str, str] = {
    # Voltage
    "voltage": "voltage",
    "rated voltage": "voltage",
    "rated_voltage": "voltage",
    "voltage (v)": "voltage",
    "supply voltage": "voltage",
    "nominal voltage": "voltage",
    "operating voltage": "voltage",
    "input voltage": "voltage",
    "line voltage": "voltage",

    # Power
    "power": "power",
    "rated power": "power",
    "rated_power": "power",
    "power (kw)": "power",
    "power (hp)": "power",
    "power output": "power",
    "motor power": "power",
    "shaft power": "power",
    "input power": "power",
    "output power": "power",

    # Speed / RPM
    "speed": "rotational_speed",
    "rated speed": "rotational_speed",
    "rpm": "rotational_speed",
    "rotational speed": "rotational_speed",
    "motor speed": "rotational_speed",
    "shaft speed": "rotational_speed",
    "synchronous speed": "rotational_speed",
    "r/min": "rotational_speed",
    "rev/min": "rotational_speed",

    # Pressure
    "pressure": "pressure",
    "rated pressure": "pressure",
    "max pressure": "pressure",
    "maximum pressure": "pressure",
    "operating pressure": "pressure",
    "working pressure": "pressure",
    "pressure (bar)": "pressure",
    "pressure (psi)": "pressure",

    # Weight / Mass
    "weight": "weight",
    "net weight": "weight",
    "gross weight": "weight",
    "mass": "weight",
    "weight (kg)": "weight",
    "net weight (kg)": "weight",

    # Frequency
    "frequency": "frequency",
    "supply frequency": "frequency",
    "frequency (hz)": "frequency",
    "electrical frequency": "frequency",
    "line frequency": "frequency",
    "hz": "frequency",

    # Current
    "current": "current",
    "rated current": "current",
    "full load current": "current",
    "flc": "current",
    "current (a)": "current",

    # Flow
    "flow": "flow_rate",
    "flow rate": "flow_rate",
    "nominal flow": "flow_rate",
    "rated flow": "flow_rate",
    "flow (l/min)": "flow_rate",

    # Dimensions
    "length": "length",
    "width": "width",
    "height": "height",
    "depth": "length",

    # Temperature
    "min temperature": "temperature_min",
    "min temp": "temperature_min",
    "max temperature": "temperature_max",
    "max temp": "temperature_max",
    "ambient temperature": "temperature_max",
}

# Unit patterns embedded in column names (e.g. "Rated Power (HP)")
UNIT_IN_COL_PATTERN = re.compile(r"\(([^)]+)\)\s*$")

# Regex to extract numeric value and unit from a cell string
VALUE_UNIT_RE = re.compile(
    r"([-+]?\d*\.?\d+)\s*"
    r"(kW|HP|W|MW|V|kV|A|mA|Hz|RPM|r/min|bar|psi|MPa|kPa|Pa|kg|g|lb|lbs|t|L/min|lpm|m3/h|mm|cm|m|°C|°F|K)?",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class CellValue:
    """A single extracted attribute value from a spreadsheet cell."""
    sheet_name: str
    row_number: int          # 1-based row number in the data (after header)
    column_name: str         # Original column header as-is
    canonical_attr: str      # Mapped canonical attribute name
    raw_value: str           # Original cell content as string
    numeric_value: Optional[float] = None
    raw_unit: Optional[str] = None
    unit_from_col_header: Optional[str] = None  # Unit embedded in column header


@dataclass
class ParsedSpreadsheet:
    filename: str
    file_hash: str
    file_type: str           # "xlsx", "csv", "xlsm", "xls"
    sheet_names: List[str] = field(default_factory=list)
    records: List[CellValue] = field(default_factory=list)
    validation_messages: List[str] = field(default_factory=list)
    raw_text: str = ""
    parse_error: Optional[str] = None
    row_count: int = 0


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalize_col_name(col: str) -> str:
    """Lowercase + strip extra spaces for column mapping lookup."""
    return re.sub(r"\s+", " ", str(col).strip().lower())


def _map_column(col: str) -> Optional[tuple[str, Optional[str]]]:
    """
    Map a raw column header to (canonical_attr, unit_hint).
    Returns None if no mapping found.
    """
    normalized = _normalize_col_name(col)

    # Direct match
    if normalized in COLUMN_MAPPING:
        # Extract unit hint from column header
        unit_match = UNIT_IN_COL_PATTERN.search(normalized)
        unit_hint = unit_match.group(1).strip() if unit_match else None
        return COLUMN_MAPPING[normalized], unit_hint

    # Strip parenthetical unit and try again: "Rated Voltage (V)" → "Rated Voltage"
    stripped = UNIT_IN_COL_PATTERN.sub("", normalized).strip()
    if stripped in COLUMN_MAPPING:
        unit_match = UNIT_IN_COL_PATTERN.search(normalized)
        unit_hint = unit_match.group(1).strip() if unit_match else None
        return COLUMN_MAPPING[stripped], unit_hint

    return None


def _extract_value_unit(cell_str: str, col_unit_hint: Optional[str] = None) -> tuple[str, Optional[float], Optional[str]]:
    """
    Parse a cell string like '415 V' or '7.5kW' or '1440 RPM' into
    (raw_value, numeric, unit). Falls back to col_unit_hint if no unit in cell.
    """
    cell_str = str(cell_str).strip()
    if not cell_str or cell_str.lower() in ("nan", "none", "", "-", "n/a", "na"):
        return cell_str, None, None

    match = VALUE_UNIT_RE.match(cell_str)
    if match:
        num_str = match.group(1)
        unit_str = match.group(2)
        try:
            numeric = float(num_str)
        except ValueError:
            numeric = None
        unit = unit_str.strip() if unit_str else col_unit_hint
        return cell_str, numeric, unit

    # Cell might just be a plain number (e.g. "415")
    try:
        numeric = float(cell_str.replace(",", ""))
        return cell_str, numeric, col_unit_hint
    except ValueError:
        pass

    return cell_str, None, None


# ---------------------------------------------------------------------------
# Main parsing function
# ---------------------------------------------------------------------------
def parse_excel(file_path: str, file_hash: str) -> ParsedSpreadsheet:
    """
    Parse a CSV, XLSX, XLSM or XLS file into a ParsedSpreadsheet.
    Extracts per-cell provenance: sheet, row, column, raw_value.
    """
    path = Path(file_path)
    if not path.exists():
        return ParsedSpreadsheet(
            filename=path.name, file_hash=file_hash, file_type="unknown",
            parse_error=f"File not found: {file_path}"
        )

    ext = path.suffix.lower().lstrip(".")
    if ext not in ("csv", "xlsx", "xlsm", "xls"):
        return ParsedSpreadsheet(
            filename=path.name, file_hash=file_hash, file_type=ext,
            parse_error=f"Unsupported file format: .{ext}"
        )

    try:
        import pandas as pd
    except ImportError:
        return ParsedSpreadsheet(
            filename=path.name, file_hash=file_hash, file_type=ext,
            parse_error="pandas is not installed. Run: pip install pandas openpyxl"
        )

    result = ParsedSpreadsheet(
        filename=path.name,
        file_hash=file_hash,
        file_type=ext,
    )

    try:
        # ---- Load sheets ----
        if ext == "csv":
            sheets = {"Sheet1": _load_csv(path, pd)}
        elif ext in ("xlsx", "xlsm"):
            sheets = _load_xlsx(path, pd, ext)
        elif ext == "xls":
            sheets = _load_xls(path, pd)
        else:
            sheets = {}

        if not sheets:
            result.parse_error = "No readable sheets found in file"
            return result

        result.sheet_names = list(sheets.keys())
        all_text_parts = []

        for sheet_name, df in sheets.items():
            if df is None or df.empty:
                result.validation_messages.append(f"Sheet '{sheet_name}' is empty or unreadable")
                continue

            # Drop fully empty rows
            df = df.dropna(how="all")

            # Validate headers
            if df.columns.tolist() == list(range(len(df.columns))):
                result.validation_messages.append(
                    f"Sheet '{sheet_name}': No header row detected — skipping"
                )
                continue

            # Check for duplicate column names
            col_names = [str(c) for c in df.columns]
            seen_cols = set()
            dup_cols = set()
            for c in col_names:
                norm = _normalize_col_name(c)
                if norm in seen_cols:
                    dup_cols.add(c)
                seen_cols.add(norm)
            if dup_cols:
                result.validation_messages.append(
                    f"Sheet '{sheet_name}': Duplicate columns detected: {', '.join(dup_cols)}"
                )

            # Count missing values in key columns
            mapped_count = sum(1 for c in col_names if _map_column(c) is not None)
            if mapped_count == 0:
                result.validation_messages.append(
                    f"Sheet '{sheet_name}': No recognized attribute columns found (columns: {', '.join(col_names[:8])})"
                )
                continue

            # Process each row
            row_count = 0
            for row_idx, row in df.iterrows():
                row_num = int(row_idx) + 2  # +2 because header is row 1
                row_has_data = False

                for col in col_names:
                    mapping = _map_column(col)
                    if mapping is None:
                        continue

                    canonical_attr, col_unit_hint = mapping
                    cell_val = row.get(col)

                    # Skip empty cells
                    if cell_val is None or (isinstance(cell_val, float) and cell_val != cell_val):
                        continue

                    raw_str, numeric, unit = _extract_value_unit(str(cell_val), col_unit_hint)
                    if not raw_str or raw_str.lower() in ("nan", "none", ""):
                        continue

                    cell = CellValue(
                        sheet_name=sheet_name,
                        row_number=row_num,
                        column_name=col,
                        canonical_attr=canonical_attr,
                        raw_value=raw_str,
                        numeric_value=numeric,
                        raw_unit=unit,
                        unit_from_col_header=col_unit_hint,
                    )
                    result.records.append(cell)
                    all_text_parts.append(f"{canonical_attr}: {raw_str}")
                    row_has_data = True

                if row_has_data:
                    row_count += 1

            result.row_count += row_count

        result.raw_text = "\n".join(all_text_parts)

    except Exception as e:
        logger.error(f"Excel parsing failed for {file_path}: {e}")
        result.parse_error = str(e)

    return result


def _load_csv(path: Path, pd) -> "pd.DataFrame":
    try:
        return pd.read_csv(str(path), dtype=str, on_bad_lines="warn")
    except Exception as e:
        logger.warning(f"CSV load warning: {e}")
        return pd.read_csv(str(path), dtype=str, error_bad_lines=False)


def _load_xlsx(path: Path, pd, ext: str) -> Dict[str, "pd.DataFrame"]:
    try:
        xl = pd.ExcelFile(str(path), engine="openpyxl")
        return {name: xl.parse(name, dtype=str) for name in xl.sheet_names}
    except Exception as e:
        logger.error(f"XLSX load failed: {e}")
        return {}


def _load_xls(path: Path, pd) -> Dict[str, "pd.DataFrame"]:
    try:
        xl = pd.ExcelFile(str(path), engine="xlrd")
        return {name: xl.parse(name, dtype=str) for name in xl.sheet_names}
    except Exception as e:
        logger.error(f"XLS load failed: {e}")
        return {}


def validate_excel_file(filename: str, content_type: str, size_bytes: int) -> tuple[bool, Optional[str]]:
    """Validate uploaded file before processing."""
    ext = Path(filename).suffix.lower()
    if ext not in (".csv", ".xlsx", ".xlsm", ".xls"):
        return False, f"Unsupported file type: '{ext}'. Allowed: .csv, .xlsx, .xlsm, .xls"

    allowed_mimes = {
        "text/csv", "application/csv",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel.sheet.macroenabled.12",
        "application/octet-stream",
    }
    if content_type and content_type.split(";")[0].strip() not in allowed_mimes:
        logger.warning(f"Excel MIME type '{content_type}' not in allowed list — proceeding based on extension")

    MAX_SIZE = 50 * 1024 * 1024  # 50MB
    if size_bytes > MAX_SIZE:
        return False, f"File too large: {size_bytes // (1024*1024)}MB. Maximum: 50MB"

    # Sanitize filename
    safe_chars = re.sub(r"[^a-zA-Z0-9._\-\s]", "_", filename)
    if safe_chars != filename:
        logger.info(f"Filename sanitized: '{filename}' → '{safe_chars}'")

    return True, None
