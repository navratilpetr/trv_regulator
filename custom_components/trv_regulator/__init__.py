"""TRV Regulator integration."""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    DOMAIN,
    DEFAULT_LEARNING_CYCLES,
    DEFAULT_DESIRED_OVERSHOOT,
    DEFAULT_MIN_HEATING_DURATION,
    DEFAULT_MAX_HEATING_DURATION,
    DEFAULT_MAX_VALID_OVERSHOOT,
    DEFAULT_COOLDOWN_DURATION,
    TARGET_DEBOUNCE_DELAY,
)
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


async def async_migrate_entry(hass, config_entry: ConfigEntry) -> bool:
    """Migrovat starou konfiguraci."""
    if config_entry.version == 1:
        new_data = {**config_entry.data}
        new_options = {**config_entry.options}
        
        # Odstranit zastaralý parametr learning_speed
        new_data.pop("learning_speed", None)
        new_options.pop("learning_speed", None)
        
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            options=new_options,
            version=2
        )
        
        _LOGGER.info(
            f"Migrace konfigurace z verze 1 na 2 "
            f"(odstraněn nepoužívaný parametr learning_speed)"
        )
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Nastavení po přidání přes UI."""
    # Počkat až budou dostupné všechny entity
    await _wait_for_entities(hass, entry)
    
    # Vytvoř RoomController z config entry
    trv_entities = [
        {"entity": entity_id, "enabled": True}
        for entity_id in entry.data["trv_entities"]
    ]

    # Merge window_entities and door_entities (for backward compatibility)
    # Prefer options if exists, otherwise use data
    window_entities = entry.options.get("window_entities", entry.data.get("window_entities", []))
    door_entities = entry.data.get("door_entities", [])
    all_window_entities = list(window_entities) + list(door_entities)

    # Helper function to read from options or data (with backward compatibility for vent_delay)
    def get_config_value(key, default):
        value = entry.options.get(key, entry.data.get(key))
        # Backward compatibility: if window_open_delay not found, try vent_delay
        if value is None and key == "window_open_delay":
            value = entry.options.get("vent_delay", entry.data.get("vent_delay"))
        return value if value is not None else default

    room = RoomController(
        hass,
        room_name=entry.data["room_name"],
        temperature_entity=entry.data["temperature_entity"],
        target_entity=entry.data["target_entity"],
        trv_entities=trv_entities,
        window_entities=all_window_entities,
        hysteresis=get_config_value("hysteresis", 0.3),
        window_open_delay=get_config_value("window_open_delay", 120),
        learning_cycles_required=get_config_value("learning_cycles_required", DEFAULT_LEARNING_CYCLES),
        desired_overshoot=get_config_value("desired_overshoot", DEFAULT_DESIRED_OVERSHOOT),
        min_heating_duration=get_config_value("min_heating_duration", DEFAULT_MIN_HEATING_DURATION),
        max_heating_duration=get_config_value("max_heating_duration", DEFAULT_MAX_HEATING_DURATION),
        max_valid_overshoot=get_config_value("max_valid_overshoot", DEFAULT_MAX_VALID_OVERSHOOT),
        cooldown_duration=get_config_value("cooldown_duration", DEFAULT_COOLDOWN_DURATION),
    )

    # Vytvoř coordinator
    coordinator = TrvRegulatorCoordinator(hass, room)

    # Set refresh callback to avoid circular import
    room.set_refresh_callback(coordinator.async_request_refresh)

    # Track změny relevantních entit
    # Target entity má debounce přímo v room_controller
    tracked_entities = [
        entry.data["temperature_entity"],
        entry.data["target_entity"],
        *entry.data["trv_entities"],
        *all_window_entities,
    ]

    async def _entity_listener(event):
        """Listener pro změny entit."""
        # Pro target_entity nechat room_controller zpracovat debounce
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
