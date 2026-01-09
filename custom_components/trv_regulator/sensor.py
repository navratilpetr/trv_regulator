"""Sensor platform pro TRV Regulator diagnostiku."""
import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
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
        TrvGainSensor(coordinator, room_name, entry.entry_id),
        TrvOffsetSensor(coordinator, room_name, entry.entry_id),
        TrvOscillationSensor(coordinator, room_name, entry.entry_id),
        TrvTargetSensor(coordinator, room_name, entry.entry_id),
        TrvCommandsSensor(coordinator, room_name, entry.entry_id),
        TrvLearnedGainSensor(coordinator, room_name, entry.entry_id),
    ]
    
    async_add_entities(sensors)


class TrvBaseSensor(CoordinatorEntity, SensorEntity):
    """Základní třída pro TRV senzory."""

    def __init__(self, coordinator, room_name: str, entry_id: str, sensor_type: str):
        """Inicializace senzoru."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._sensor_type = sensor_type
        # Použít DOMAIN v unique_id pro prevenci konfliktů
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{sensor_type}"
        self._attr_has_entity_name = True


class TrvGainSensor(TrvBaseSensor):
    """Senzor pro aktuální gain hodnotu."""

    def __init__(self, coordinator, room_name: str, entry_id: str):
        """Inicializace gain senzoru."""
        super().__init__(coordinator, room_name, entry_id, "gain")
        self._attr_name = f"TRV {room_name} Gain"
        self._attr_icon = "mdi:tune"

    @property
    def native_value(self):
        """Vrací aktuální gain."""
        return self.coordinator.room.gain


class TrvOffsetSensor(TrvBaseSensor):
    """Senzor pro aktuální offset hodnotu."""

    def __init__(self, coordinator, room_name: str, entry_id: str):
        """Inicializace offset senzoru."""
        super().__init__(coordinator, room_name, entry_id, "offset")
        self._attr_name = f"TRV {room_name} Offset"
        self._attr_icon = "mdi:delta"
        self._attr_native_unit_of_measurement = "°C"

    @property
    def native_value(self):
        """Vrací aktuální offset."""
        return self.coordinator.room.offset


class TrvOscillationSensor(TrvBaseSensor):
    """Senzor pro oscilaci teploty."""

    def __init__(self, coordinator, room_name: str, entry_id: str):
        """Inicializace oscillation senzoru."""
        super().__init__(coordinator, room_name, entry_id, "oscillation")
        self._attr_name = f"TRV {room_name} Oscillation"
        self._attr_icon = "mdi:wave"
        self._attr_native_unit_of_measurement = "°C"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self):
        """Vrací oscilaci teploty."""
        return round(self.coordinator.room.calculate_oscillation(), 2)


class TrvTargetSensor(TrvBaseSensor):
    """Senzor pro cílovou teplotu poslanou na TRV."""

    def __init__(self, coordinator, room_name: str, entry_id: str):
        """Inicializace target senzoru."""
        super().__init__(coordinator, room_name, entry_id, "trv_target")
        self._attr_name = f"TRV {room_name} Target Temperature"
        self._attr_icon = "mdi:thermometer-lines"
        self._attr_native_unit_of_measurement = "°C"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self):
        """Vrací poslední vypočítanou cílovou teplotu."""
        target = self.coordinator.room.last_trv_target
        if target is not None:
            return round(target, 1)
        return None


class TrvCommandsSensor(TrvBaseSensor):
    """Senzor pro celkový počet odeslaných příkazů."""

    def __init__(self, coordinator, room_name: str, entry_id: str):
        """Inicializace commands senzoru."""
        super().__init__(coordinator, room_name, entry_id, "commands_total")
        self._attr_name = f"TRV {room_name} Commands Total"
        self._attr_icon = "mdi:counter"

    @property
    def native_value(self):
        """Vrací celkový počet příkazů."""
        return self.coordinator.room.commands_total


class TrvLearnedGainSensor(TrvBaseSensor):
    """Senzor pro naučený gain (placeholder pro budoucí ML)."""

    def __init__(self, coordinator, room_name: str, entry_id: str):
        """Inicializace learned gain senzoru."""
        super().__init__(coordinator, room_name, entry_id, "learned_gain")
        self._attr_name = f"TRV {room_name} Learned Gain"
        self._attr_icon = "mdi:brain"

    @property
    def native_value(self):
        """Vrací naučený gain."""
        learned = self.coordinator.room.get_learned_gain()
        if learned is not None:
            return round(learned, 1)
        return None
