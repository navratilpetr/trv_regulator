"""Sensor platform pro TRV Regulator diagnostiku."""
import logging
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
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
    """Nastavení sensor platformy z config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    room_name = entry.data["room_name"]
    
    sensors = [
        TrvStateSensor(coordinator, room_name, entry.entry_id),
        TrvLearningSensor(coordinator, room_name, entry.entry_id),
        TrvLastCycleSensor(coordinator, room_name, entry.entry_id),
        TrvHistorySensor(coordinator, room_name, entry.entry_id),
    ]
    
    async_add_entities(sensors)


class TrvBaseSensor(CoordinatorEntity, SensorEntity):
    """Základní třída pro TRV senzory."""

    def __init__(self, coordinator, room_name: str, entry_id: str, sensor_type: str):
        """Inicializace senzoru."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._sensor_type = sensor_type
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{sensor_type}"
        self._attr_has_entity_name = True


class TrvStateSensor(TrvBaseSensor):
    """Senzor pro stav automatu."""

    def __init__(self, coordinator, room_name: str, entry_id: str):
        """Inicializace state senzoru."""
        super().__init__(coordinator, room_name, entry_id, "state")
        self._attr_name = f"TRV {room_name} State"
        self._attr_icon = "mdi:state-machine"

    @property
    def native_value(self):
        """Vrací aktuální stav."""
        return self.coordinator.room.state

    @property
    def extra_state_attributes(self):
        """Vrací dodatečné atributy."""
        room = self.coordinator.room
        
        # Načíst aktuální teploty
        temp = room._get_temperature()
        target = room._get_target()
        
        attrs = {
            "current_temp": temp,
            "target_temp": target,
        }
        
        # Přidat informace o topení pokud probíhá
        if room.state == "heating":
            if room._heating_start_time:
                attrs["heating_start_time"] = datetime.fromtimestamp(
                    room._heating_start_time
                ).isoformat()
                attrs["heating_elapsed_seconds"] = int(room.heating_elapsed_seconds or 0)
                
                if room.heating_remaining_seconds is not None:
                    attrs["heating_remaining_seconds"] = int(room.heating_remaining_seconds)
        
        return attrs


class TrvLearningSensor(TrvBaseSensor):
    """Senzor pro učení."""

    def __init__(self, coordinator, room_name: str, entry_id: str):
        """Inicializace learning senzoru."""
        super().__init__(coordinator, room_name, entry_id, "learning")
        self._attr_name = f"TRV {room_name} Learning"
        self._attr_icon = "mdi:school"

    @property
    def native_value(self):
        """Vrací stav učení."""
        return "learning" if self.coordinator.room.is_learning else "learned"

    @property
    def extra_state_attributes(self):
        """Vrací dodatečné atributy."""
        room = self.coordinator.room
        
        attrs = {
            "valid_cycles": room.valid_cycles_count,
            "required_cycles": room._learning_cycles_required,
            "learning_speed": room._learning_speed,
        }
        
        if room.avg_heating_duration is not None:
            attrs["avg_heating_duration"] = int(room.avg_heating_duration)
        
        if room.time_offset is not None:
            attrs["time_offset"] = int(room.time_offset)
        
        if room.avg_overshoot is not None:
            attrs["avg_overshoot"] = round(room.avg_overshoot, 2)
        
        return attrs


class TrvLastCycleSensor(TrvBaseSensor):
    """Senzor pro poslední cyklus."""

    def __init__(self, coordinator, room_name: str, entry_id: str):
        """Inicializace last cycle senzoru."""
        super().__init__(coordinator, room_name, entry_id, "last_cycle")
        self._attr_name = f"TRV {room_name} Last Cycle"
        self._attr_icon = "mdi:history"

    @property
    def native_value(self):
        """Vrací timestamp posledního cyklu."""
        cycle = self.coordinator.room.last_cycle
        if cycle and "timestamp" in cycle:
            return datetime.fromtimestamp(cycle["timestamp"]).isoformat()
        return None

    @property
    def extra_state_attributes(self):
        """Vrací dodatečné atributy."""
        cycle = self.coordinator.room.last_cycle
        if not cycle:
            return {}
        
        attrs = {}
        
        if "heating_duration" in cycle:
            attrs["heating_duration"] = int(cycle["heating_duration"])
        
        if "overshoot" in cycle:
            attrs["overshoot"] = round(cycle["overshoot"], 2)
        
        if "start_temp" in cycle:
            attrs["start_temp"] = round(cycle["start_temp"], 1)
        
        if "stop_temp" in cycle:
            attrs["stop_temp"] = round(cycle["stop_temp"], 1)
        
        if "max_temp" in cycle:
            attrs["max_temp"] = round(cycle["max_temp"], 1)
        
        if "valid" in cycle:
            attrs["valid"] = cycle["valid"]
        
        if "invalidation_reason" in cycle:
            attrs["invalidation_reason"] = cycle["invalidation_reason"]
        
        return attrs


class TrvHistorySensor(TrvBaseSensor):
    """Senzor pro historii cyklů."""

    def __init__(self, coordinator, room_name: str, entry_id: str):
        """Inicializace history senzoru."""
        super().__init__(coordinator, room_name, entry_id, "history")
        self._attr_name = f"TRV {room_name} History"
        self._attr_icon = "mdi:chart-line"

    @property
    def native_value(self):
        """Vrací počet cyklů v historii."""
        return len(self.coordinator.room.history)

    @property
    def extra_state_attributes(self):
        """Vrací dodatečné atributy."""
        history = self.coordinator.room.history
        
        # Vrátit celou historii (max 100 cyklů)
        return {
            "cycles": history
        }
