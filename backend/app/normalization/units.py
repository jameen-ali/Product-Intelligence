"""
Deterministic unit conversion engine for IPTE.
All conversions use fixed, auditable factors. No LLM arithmetic.
"""
from typing import Optional, Tuple

# Canonical output units for each unit_type
CANONICAL_UNIT: dict[str, str] = {
    "power": "kW",
    "pressure": "bar",
    "flow": "L/min",
    "mass": "kg",
    "length": "mm",
    "temperature_min": "°C",
    "temperature_max": "°C",
    "voltage": "V",
    "current": "A",
    "rotational_speed": "RPM",
}

# Conversion table: (from_unit_normalised, to_unit_normalised) -> lambda
# Normalised = lowercase, stripped of spaces
_CONVERSIONS: dict[Tuple[str, str], callable] = {
    # Power
    ("hp", "kw"): lambda v: round(v * 0.7457, 6),
    ("w", "kw"): lambda v: round(v / 1000.0, 6),
    ("mw", "kw"): lambda v: round(v * 1000.0, 6),
    ("kw", "kw"): lambda v: v,
    ("kw", "hp"): lambda v: round(v / 0.7457, 6),
    ("kw", "w"): lambda v: round(v * 1000.0, 6),
    ("hp", "w"): lambda v: round(v * 745.7, 6),
    ("w", "hp"): lambda v: round(v / 745.7, 6),

    # Pressure
    ("bar", "psi"): lambda v: round(v * 14.5038, 4),
    ("psi", "bar"): lambda v: round(v / 14.5038, 6),
    ("mpa", "bar"): lambda v: round(v * 10.0, 4),
    ("bar", "mpa"): lambda v: round(v / 10.0, 6),
    ("pa", "bar"): lambda v: round(v / 100000.0, 9),
    ("kpa", "bar"): lambda v: round(v / 100.0, 7),
    ("bar", "bar"): lambda v: v,
    ("psi", "psi"): lambda v: v,

    # Flow rate
    ("l/min", "l/min"): lambda v: v,
    ("lpm", "l/min"): lambda v: v,
    ("ml/min", "l/min"): lambda v: round(v / 1000.0, 9),
    ("gpm", "l/min"): lambda v: round(v * 3.78541, 6),   # US gallon
    ("l/s", "l/min"): lambda v: round(v * 60.0, 4),
    ("m3/h", "l/min"): lambda v: round(v * 1000.0 / 60.0, 6),

    # Mass
    ("kg", "kg"): lambda v: v,
    ("g", "kg"): lambda v: round(v / 1000.0, 9),
    ("lb", "kg"): lambda v: round(v / 2.20462, 6),
    ("kg", "lb"): lambda v: round(v * 2.20462, 4),
    ("lbs", "kg"): lambda v: round(v / 2.20462, 6),
    ("t", "kg"): lambda v: round(v * 1000.0, 4),

    # Length
    ("mm", "mm"): lambda v: v,
    ("cm", "mm"): lambda v: round(v * 10.0, 4),
    ("m", "mm"): lambda v: round(v * 1000.0, 4),
    ("inch", "mm"): lambda v: round(v * 25.4, 4),
    ("in", "mm"): lambda v: round(v * 25.4, 4),
    ("\"", "mm"): lambda v: round(v * 25.4, 4),
    ("mm", "inch"): lambda v: round(v / 25.4, 6),

    # Temperature
    ("°c", "°c"): lambda v: v,
    ("c", "°c"): lambda v: v,
    ("degc", "°c"): lambda v: v,
    ("°f", "°c"): lambda v: round((v - 32) * 5.0 / 9.0, 4),
    ("f", "°c"): lambda v: round((v - 32) * 5.0 / 9.0, 4),
    ("degf", "°c"): lambda v: round((v - 32) * 5.0 / 9.0, 4),
    ("°c", "°f"): lambda v: round(v * 9.0 / 5.0 + 32, 4),
    ("k", "°c"): lambda v: round(v - 273.15, 4),

    # Voltage — no cross-unit conversion
    ("v", "v"): lambda v: v,
    ("kv", "v"): lambda v: round(v * 1000.0, 4),
    ("mv", "v"): lambda v: round(v / 1000.0, 6),

    # Current — no cross-unit conversion
    ("a", "a"): lambda v: v,
    ("ma", "a"): lambda v: round(v / 1000.0, 6),
    ("ka", "a"): lambda v: round(v * 1000.0, 4),

    # Rotational speed — no cross-unit conversion
    ("rpm", "rpm"): lambda v: v,
    ("r/min", "rpm"): lambda v: v,
    ("rev/min", "rpm"): lambda v: v,
    ("rps", "rpm"): lambda v: round(v * 60.0, 4),
}

def _normalise_unit(unit: str) -> str:
    return unit.strip().lower().replace(" ", "")

def convert(value: float, from_unit: str, to_unit: str) -> Optional[float]:
    """Convert value from from_unit to to_unit. Returns None if conversion not supported."""
    key = (_normalise_unit(from_unit), _normalise_unit(to_unit))
    fn = _CONVERSIONS.get(key)
    if fn is None:
        return None
    return fn(value)

class NormalisationResult:
    def __init__(self, raw_value: float, raw_unit: str, normalized_value: Optional[float],
                 normalized_unit: Optional[str], status: str, notes: str = ""):
        self.raw_value = raw_value
        self.raw_unit = raw_unit
        self.normalized_value = normalized_value
        self.normalized_unit = normalized_unit
        self.status = status  # "OK", "IDENTITY", "UNSUPPORTED"
        self.notes = notes

    def to_dict(self) -> dict:
        return {
            "raw_value": self.raw_value,
            "raw_unit": self.raw_unit,
            "normalized_value": self.normalized_value,
            "normalized_unit": self.normalized_unit,
            "normalization_status": self.status,
            "notes": self.notes,
        }

def normalise_to_canonical(value: float, unit: str, unit_type: Optional[str] = None) -> NormalisationResult:
    """
    Normalise a raw value to the canonical unit for its type.
    If unit_type is given, uses CANONICAL_UNIT to determine target.
    Otherwise attempts identity conversion.
    """
    canonical = CANONICAL_UNIT.get(unit_type, "") if unit_type else ""

    if canonical:
        if _normalise_unit(unit) == _normalise_unit(canonical):
            return NormalisationResult(value, unit, value, canonical, "IDENTITY")
        result = convert(value, unit, canonical)
        if result is not None:
            return NormalisationResult(value, unit, result, canonical, "OK")
        return NormalisationResult(value, unit, None, None, "UNSUPPORTED",
                                   f"No conversion from '{unit}' to '{canonical}'")

    # No unit_type provided: try identity pass-through
    return NormalisationResult(value, unit, value, unit, "IDENTITY",
                               "No unit_type provided; stored as-is")

def are_equivalent(value1: float, unit1: str, value2: float, unit2: str,
                   tolerance: float = 0.02) -> bool:
    """
    Check whether two values in (possibly different) units represent the same quantity.
    Uses bidirectional conversion attempt. Tolerance is 2% by default.
    """
    u1 = _normalise_unit(unit1)
    u2 = _normalise_unit(unit2)
    if u1 == u2:
        return abs(value1 - value2) / max(abs(value1), 1e-9) <= tolerance

    converted = convert(value1, unit1, unit2)
    if converted is not None:
        return abs(converted - value2) / max(abs(value2), 1e-9) <= tolerance

    converted_back = convert(value2, unit2, unit1)
    if converted_back is not None:
        return abs(value1 - converted_back) / max(abs(value1), 1e-9) <= tolerance

    return False
