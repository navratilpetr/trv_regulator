"""Binary sensor platform pro TRV Regulator."""
import logging

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Nastavení binary sensor platformy z config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    room_name = entry.data["room_name"]
    
    sensors = [
        TrvCommunicationProblemSensor(coordinator, room_name, entry.entry_id),
    ]
    
    async_add_entities(sensors)


class TrvCommunicationProblemSensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor pro detekci komunikačních problémů s TRV."""
    
    def __init__(self, coordinator, room_name: str, entry_id: str):
        """Inicializace binary sensoru."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._entry_id = entry_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_communication_problem"
        self._attr_name = "Communication Problem"
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM
        self._attr_icon = "mdi:connection"
        self._attr_has_entity_name = True
    
    @property
    def device_info(self):
        """Informace o zařízení."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"TRV Regulator {self._room_name}",
            "manufacturer": "Custom",
            "model": "TRV Regulator",
            "via_device": None,
        }
    
    @property
    def is_on(self):
        """
        ON = poslední příkaz SELHAL (last_seen unchanged)
        OFF = poslední příkaz OK (last_seen changed)
        """
        room = self.coordinator.room
        
        # Zkontroluj všechny TRV v místnosti
        for entity_id, trv_stats in room._reliability_tracker._trv_stats.items():
            if trv_stats.get("last_command_failed", False):
                return True  # ERROR
        
        return False  # OK
    
    @property
    def extra_state_attributes(self):
        """Info o problému."""
        room = self.coordinator.room
        problem_trvs = []
        
        for entity_id, trv_stats in room._reliability_tracker._trv_stats.items():
            if trv_stats.get("last_command_failed", False):
                problem_trvs.append({
                    "entity_id": entity_id,
                    "last_failure_time": trv_stats.get("last_failure_time"),
                    "last_failure_reason": trv_stats.get("last_failure_reason"),
                })
        
        return {
            "problem_trvs": problem_trvs,
            "total_problem_trvs": len(problem_trvs),
            "total_failures_24h": room._reliability_tracker.get_failed_commands_24h() if hasattr(room._reliability_tracker, 'get_failed_commands_24h') else 0,
        }
