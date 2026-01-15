"""Test constants for TRV Regulator."""
from custom_components.trv_regulator.const import (
    STATE_IDLE,
    STATE_HEATING,
    STATE_COOLDOWN,
    STATE_VENT,
    STATE_ERROR,
    TRV_ON,
    TRV_OFF,
    DEFAULT_HYSTERESIS,
    DEFAULT_WINDOW_OPEN_DELAY,
    DEFAULT_LEARNING_CYCLES,
    DOMAIN,
)


def test_domain():
    """Test domain constant."""
    assert DOMAIN == "trv_regulator"


def test_states():
    """Test state constants."""
    assert STATE_IDLE == "idle"
    assert STATE_HEATING == "heating"
    assert STATE_COOLDOWN == "cooldown"
    assert STATE_VENT == "vent"
    assert STATE_ERROR == "error"


def test_trv_commands():
    """Test TRV command constants."""
    assert TRV_ON == {"hvac_mode": "heat", "temperature": 35}
    assert TRV_OFF == {"hvac_mode": "heat", "temperature": 5}


def test_default_values():
    """Test default configuration values."""
    assert DEFAULT_HYSTERESIS == 0.3
    assert DEFAULT_WINDOW_OPEN_DELAY == 120
    assert DEFAULT_LEARNING_CYCLES == 10
