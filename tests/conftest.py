"""Test configuration for TRV Regulator."""
import pytest
from unittest.mock import MagicMock, patch
from homeassistant.core import HomeAssistant


@pytest.fixture
def hass():
    """Fixture for Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.states = MagicMock()
    hass.data = {}
    hass.config_entries = MagicMock()
    hass.services = MagicMock()
    return hass


@pytest.fixture
def mock_room_config():
    """Fixture for room configuration."""
    return {
        "room_name": "test_room",
        "temperature_entity": "sensor.test_temperature",
        "target_entity": "input_number.test_target",
        "trv_entities": [
            {"entity": "climate.test_trv", "enabled": True}
        ],
        "window_entities": ["binary_sensor.test_window"],
        "hysteresis": 0.3,
        "window_open_delay": 120,
    }
