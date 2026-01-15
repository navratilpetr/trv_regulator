"""Test RoomController for TRV Regulator."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from custom_components.trv_regulator.room_controller import RoomController
from custom_components.trv_regulator.const import STATE_IDLE, STATE_HEATING


class TestRoomController:
    """Test RoomController class."""

    @pytest.mark.asyncio
    async def test_initialization(self, hass, mock_room_config):
        """Test RoomController initialization."""
        controller = RoomController(
            hass,
            room_name=mock_room_config["room_name"],
            temperature_entity=mock_room_config["temperature_entity"],
            target_entity=mock_room_config["target_entity"],
            trv_entities=mock_room_config["trv_entities"],
            window_entities=mock_room_config["window_entities"],
            hysteresis=mock_room_config["hysteresis"],
            window_open_delay=mock_room_config["window_open_delay"],
        )

        assert controller._room_name == "test_room"
        assert controller._state == STATE_IDLE
        assert controller._is_learning is True
        assert controller._valid_cycles_count == 0

    @pytest.mark.asyncio
    async def test_properties(self, hass, mock_room_config):
        """Test RoomController properties."""
        controller = RoomController(
            hass,
            room_name=mock_room_config["room_name"],
            temperature_entity=mock_room_config["temperature_entity"],
            target_entity=mock_room_config["target_entity"],
            trv_entities=mock_room_config["trv_entities"],
            window_entities=mock_room_config["window_entities"],
            hysteresis=mock_room_config["hysteresis"],
            window_open_delay=mock_room_config["window_open_delay"],
        )

        assert controller.state == STATE_IDLE
        assert controller.is_learning is True
        assert controller.valid_cycles_count == 0
        assert controller.avg_heating_duration is None
        assert controller.time_offset == 0
        assert controller.history == []

    @pytest.mark.asyncio
    async def test_reset_cycle_state(self, hass, mock_room_config):
        """Test reset_cycle_state method."""
        controller = RoomController(
            hass,
            room_name=mock_room_config["room_name"],
            temperature_entity=mock_room_config["temperature_entity"],
            target_entity=mock_room_config["target_entity"],
            trv_entities=mock_room_config["trv_entities"],
            window_entities=mock_room_config["window_entities"],
            hysteresis=mock_room_config["hysteresis"],
            window_open_delay=mock_room_config["window_open_delay"],
        )

        # Simulate some state
        controller._heating_start_time = 123456
        controller._cooldown_start_time = 123789
        controller._current_cycle = {"test": "data"}

        # Reset
        controller.reset_cycle_state()

        # Verify reset
        assert controller._heating_start_time is None
        assert controller._cooldown_start_time is None
        assert controller._current_cycle == {}
