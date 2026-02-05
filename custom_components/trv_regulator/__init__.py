"""TRV Regulator integration."""
import asyncio
import logging
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    DEFAULT_LEARNING_CYCLES,
    DEFAULT_DESIRED_OVERSHOOT,
    DEFAULT_MIN_HEATING_DURATION,
    DEFAULT_MAX_HEATING_DURATION,
    DEFAULT_MAX_VALID_OVERSHOOT,
    DEFAULT_COOLDOWN_DURATION,
    TARGET_DEBOUNCE_DELAY,
    TRV_OFF,
)
from .coordinator import TrvRegulatorCoordinator
from .room_controller import RoomController

_LOGGER = logging.getLogger(__name__)


async def _wait_for_entities(hass, entry, max_wait=60):
    """Počká až budou dostupné všechny potřebné entity."""
    temperature_entity = entry.data.get("temperature_entity")
    target_entity = entry.data.get("target_entity")
    trv_entities = entry.data.get("trv_entities", [])
    
    # Extrahovat entity IDs z trv_entities (může být list[str] nebo list[dict])
    trv_entity_ids = []
    for trv in trv_entities:
        if isinstance(trv, dict):
            trv_entity_ids.append(trv["entity"])
        else:
            trv_entity_ids.append(trv)
    
    all_entities = [temperature_entity, target_entity] + trv_entity_ids
    
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
    
    if config_entry.version == 2:
        new_data = {**config_entry.data}
        
        # Převést TRV entities na nový formát (VERSION 3)
        old_trv_entities = new_data.get("trv_entities", [])
        if old_trv_entities and isinstance(old_trv_entities[0], str):
            new_data["trv_entities"] = [
                {
                    "entity": entity,
                    "enabled": True,
                    "last_seen_sensor": ""  # prázdné - uživatel může přidat později
                }
                for entity in old_trv_entities
            ]
        
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            version=3
        )
        
        _LOGGER.info(
            f"Migrace konfigurace z verze 2 na 3 "
            f"(trv_entities převedeny na dict formát s last_seen_sensor)"
        )
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Nastavení po přidání přes UI."""
    # Počkat až budou dostupné všechny entity
    await _wait_for_entities(hass, entry)
    
    # Vytvoř RoomController z config entry
    trv_entities_data = entry.data.get("trv_entities", [])
    
    # Normalize trv_entities - může být list[str] nebo list[dict]
    trv_entities = []
    for trv in trv_entities_data:
        if isinstance(trv, dict):
            # Již ve formátu dict
            trv_entities.append(trv)
        else:
            # String formát - konvertovat na dict
            trv_entities.append({"entity": trv, "enabled": True})

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

    # Načíst naučené parametry asynchronně
    await room._load_learned_params()

    # ✅ BEZPEČNOSTNÍ RESET PO RESTARTU
    _LOGGER.info(
        f"TRV [{room._room_name}]: "
        "Post-restart safety: Resetting to safe state (all TRVs OFF)"
    )
    await room._set_all_trv(TRV_OFF)
    
    # Zrušit případný rozpracovaný cyklus
    room.reset_cycle_state()
    
    _LOGGER.debug(
        f"TRV [{room._room_name}]: "
        "Post-restart: Cleared any in-progress heating cycle"
    )

    # Vytvoř coordinator
    coordinator = TrvRegulatorCoordinator(hass, room)

    # Set refresh callback to avoid circular import
    room.set_refresh_callback(coordinator.async_request_refresh)

    # Track změny relevantních entit
    # Target entity má debounce přímo v room_controller
    # Extrahovat entity IDs z trv_entities (může být list[str] nebo list[dict])
    trv_entity_ids = []
    for trv in trv_entities_data:
        if isinstance(trv, dict):
            trv_entity_ids.append(trv["entity"])
        else:
            trv_entity_ids.append(trv)
    
    tracked_entities = [
        entry.data["temperature_entity"],
        entry.data["target_entity"],
        *trv_entity_ids,
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

    # Registrovat service pro reset naučených parametrů
    async def handle_reset_learned_params(call):
        """Handle reset learned parameters service."""
        entity_id = call.data.get("entity_id")
        room_name = call.data.get("room")
        
        # Najít správnou místnost
        if entity_id:
            # Extrahovat room_name z entity_id
            # Formát: climate.trv_regulator_{room_name}
            room_name = entity_id.split(".")[-1].replace("trv_regulator_", "")
        
        if not room_name:
            _LOGGER.error("reset_learned_params: room or entity_id required")
            return
        
        # Najít room_controller
        domain_data = hass.data.get(DOMAIN, {})
        room = None
        
        for key, value in domain_data.items():
            try:
                # Coordinator má atribut _room, který je RoomController
                if hasattr(value, "_room") and value._room._room_name == room_name:
                    room = value._room
                    break
            except (AttributeError, TypeError):
                # Skip entries that don't match expected structure
                continue
        
        if not room:
            _LOGGER.error(f"reset_learned_params: room '{room_name}' not found")
            return
        
        # Resetovat parametry
        await room.reset_learned_params()
        
        _LOGGER.info(f"TRV [{room_name}]: Learned parameters manually reset via service")
    
    hass.services.async_register(
        DOMAIN,
        "reset_learned_params",
        handle_reset_learned_params,
        schema=vol.Schema({
            vol.Optional("entity_id"): cv.entity_id,
            vol.Optional("room"): cv.string,
        })
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Odinstalace integrace."""
    # Unload sensor platform
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor"])
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok
