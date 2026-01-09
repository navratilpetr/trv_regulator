"""TRV Regulator integration."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN
from .coordinator import TrvRegulatorCoordinator
from .room_controller import RoomController

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Nastavení po přidání přes UI."""
    # Vytvoř RoomController z config entry
    trv_entities = [
        {"entity": entity_id, "enabled": True}
        for entity_id in entry.data["trv_entities"]
    ]

    room = RoomController(
        hass,
        room_name=entry.data["room_name"],
        temperature_entity=entry.data["temperature_entity"],
        target_entity=entry.data["target_entity"],
        trv_entities=trv_entities,
        window_entities=entry.data.get("window_entities", []),
        door_entities=entry.data.get("door_entities", []),
        heating_water_temp_entity=entry.data["heating_water_temp_entity"],
        hysteresis=entry.data.get("hysteresis", 0.3),
        vent_delay=entry.data.get("vent_delay", 120),
        post_vent_duration=entry.data.get("post_vent_duration", 300),
    )

    # Vytvoř coordinator
    coordinator = TrvRegulatorCoordinator(hass, room)

    # Track změny všech relevantních entit
    tracked_entities = [
        entry.data["temperature_entity"],
        entry.data["target_entity"],
        *entry.data["trv_entities"],
        *entry.data.get("window_entities", []),
        entry.data["heating_water_temp_entity"],
    ]

    async def _entity_listener(event):
        """Listener pro změny entit."""
        await coordinator.async_request_refresh()

    async_track_state_change_event(hass, tracked_entities, _entity_listener)

    # První update
    await coordinator.async_refresh()

    # Uložit coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Odinstalace integrace."""
    hass.data[DOMAIN].pop(entry.entry_id)
    return True
