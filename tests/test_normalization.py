"""
Tests for deterministic unit normalization engine.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))

from app.normalization.units import convert, normalise_to_canonical, are_equivalent

class TestPowerConversions:
    def test_hp_to_kw(self):
        result = convert(5, "HP", "kW")
        assert result is not None
        assert abs(result - 3.7285) < 0.01, f"Expected ~3.73, got {result}"

    def test_w_to_kw(self):
        result = convert(3730, "W", "kW")
        assert result is not None
        assert abs(result - 3.73) < 0.01

    def test_kw_to_kw(self):
        result = convert(3.73, "kW", "kW")
        assert result == 3.73

    def test_5hp_3730w_equivalent(self):
        """5 HP and 3730 W must be recognized as equivalent (not a conflict)."""
        assert are_equivalent(5, "HP", 3730, "W"), "5 HP and 3730 W should be equivalent"

    def test_5hp_373kw_equivalent(self):
        assert are_equivalent(5, "HP", 3.73, "kW"), "5 HP and 3.73 kW should be equivalent"

    def test_3730w_373kw_equivalent(self):
        assert are_equivalent(3730, "W", 3.73, "kW"), "3730 W and 3.73 kW should be equivalent"


class TestPressureConversions:
    def test_bar_to_psi(self):
        result = convert(250, "bar", "psi")
        assert result is not None
        assert abs(result - 3625.95) < 1.0

    def test_psi_to_bar(self):
        result = convert(3626, "psi", "bar")
        assert result is not None
        assert abs(result - 250.0) < 0.5


class TestMassConversions:
    def test_kg_to_lb(self):
        result = convert(38, "kg", "lb")
        assert result is not None
        assert abs(result - 83.7756) < 0.01


class TestTemperatureConversions:
    def test_celsius_identity(self):
        nr = normalise_to_canonical(-10, "°C", "temperature_min")
        assert nr.normalized_value == -10
        assert nr.status in ("IDENTITY", "OK")

    def test_fahrenheit_to_celsius(self):
        result = convert(14, "°F", "°C")
        assert result is not None
        assert abs(result - (-10.0)) < 0.1


class TestNormalisationResult:
    def test_5hp_normalises_to_kw(self):
        nr = normalise_to_canonical(5, "HP", "power")
        assert nr.normalized_unit == "kW"
        assert abs(nr.normalized_value - 3.7285) < 0.01
        assert nr.raw_value == 5
        assert nr.raw_unit == "HP"
        assert nr.status == "OK"

    def test_original_preserved(self):
        nr = normalise_to_canonical(250, "bar", "pressure")
        assert nr.raw_value == 250
        assert nr.raw_unit == "bar"


class TestEquivalence:
    def test_non_equivalent_values(self):
        """230V and 220V are NOT equivalent — this would be a real conflict."""
        assert not are_equivalent(230, "V", 220, "V"), "230V and 220V should NOT be equivalent"

    def test_same_value(self):
        assert are_equivalent(230, "V", 230, "V")
