"""TRV Regulator integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN, DEFAULT_GAIN, DEFAULT_OFFSET, DEFAULT_ADAPTIVE_LEARNING
from .coordinator import TrvRegulatorCoordinator
from .room_controller import RoomController

_LOGGER = logging.getLogger(__name__)


async def _wait_for_entities(hass, entry, max_wait=60):
    """Počká až budou dostupné všechny potřebné entity."""
    temperature_entity = entry.data.get("temperature_entity")
    target_entity = entry.data.get("target_entity")
    trv_entities = entry.data.get("trv_entities", [])
    
    all_entities = [temperature_entity, target_entity] + list(trv_entities)
    
    _LOGGER.info(
        f"TRV Regulator: Čekám na dostupnost entit: {', '.join(all_entities)}"
    )
    
    for i in range(max_wait):
        all_available = True
        
        for entity_id in all_entities:
            state = hass.states.get(entity_id)
            if state is None or state.state in ("unknown", "unavailable"):
                all_available = False
                break
        
        if all_available:
            _LOGGER.info("TRV Regulator: Všechny entity jsou dostupné, spouštím")
            return
        
        await asyncio.sleep(1)
    
    _LOGGER.warning(
        f"TRV Regulator: Některé entity stále nejsou dostupné po {max_wait}s, "
        f"spouštím i tak (může chvíli trvat než se stabilizuje)"
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Nastavení po přidání přes UI."""
    # Počkat až budou dostupné všechny entity
    await _wait_for_entities(hass, entry)
    
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
        gain=entry.data.get("gain", DEFAULT_GAIN),
        offset=entry.data.get("offset", DEFAULT_OFFSET),
        adaptive_learning=entry.data.get("adaptive_learning", DEFAULT_ADAPTIVE_LEARNING),
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

    # Forward setup pro sensor platform
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Odinstalace integrace."""
    # Unload sensor platform
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok
