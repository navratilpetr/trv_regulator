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
        TrvStatsSensor(coordinator, room_name, entry.entry_id),
        TrvDiagnosticsSensor(coordinator, room_name, entry.entry_id),
    ]
    
    async_add_entities(sensors)
    
    # Summary sensor - vytvořit jen jednou pro celou integraci
    if "summary_sensor_created" not in hass.data[DOMAIN]:
        entry_ids = [
            e.entry_id 
            for e in hass.config_entries.async_entries(DOMAIN)
        ]
        summary = TrvSummarySensor(hass, entry_ids)
        async_add_entities([summary])
        hass.data[DOMAIN]["summary_sensor_created"] = True


class TrvBaseSensor(CoordinatorEntity, SensorEntity):
    """Základní třída pro TRV senzory."""

    def __init__(self, coordinator, room_name: str, entry_id: str, sensor_type: str):
        """Inicializace senzoru."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._sensor_type = sensor_type
        self._entry_id = entry_id
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{sensor_type}"
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
        temp = room.get_temperature()
        target = room.get_target()
        
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


class TrvStatsSensor(TrvBaseSensor):
    """Statistický sensor pro místnost."""

    def __init__(self, coordinator, room_name: str, entry_id: str):
        """Inicializace stats senzoru."""
        super().__init__(coordinator, room_name, entry_id, "stats")
        self._attr_name = f"TRV {room_name} Stats"
        self._attr_icon = "mdi:chart-box-outline"

    @property
    def native_value(self):
        """Vrací stav učení."""
        return "learned" if not self.coordinator.room.is_learning else "learning"

    @property
    def extra_state_attributes(self):
        """Vrací statistické atributy."""
        room = self.coordinator.room
        history = room.history
        
        if not history:
            return {
                "total_cycles": 0,
                "valid_cycles": 0,
                "invalid_cycles": 0,
            }
        
        # Základní počty
        valid_cycles = [c for c in history if c.get("valid", False)]
        invalid_cycles = [c for c in history if not c.get("valid", True)]
        total = len(history)
        valid_count = len(valid_cycles)
        invalid_count = len(invalid_cycles)
        
        attrs = {
            "total_cycles": total,
            "valid_cycles": valid_count,
            "invalid_cycles": invalid_count,
            "success_rate": round((valid_count / total * 100) if total > 0 else 0, 1),
        }
        
        # Statistiky z validních cyklů
        if valid_cycles:
            durations = [c.get("heating_duration", 0) for c in valid_cycles]
            overshoots = [c.get("overshoot", 0) for c in valid_cycles]
            
            attrs.update({
                "avg_heating_time": int(sum(durations) / len(durations)),
                "min_heating_time": int(min(durations)),
                "max_heating_time": int(max(durations)),
                "avg_overshoot": round(sum(overshoots) / len(overshoots), 2),
                "min_overshoot": round(min(overshoots), 2),
                "max_overshoot": round(max(overshoots), 2),
            })
        
        # Časové info
        if history:
            first = datetime.fromtimestamp(history[0]["timestamp"])
            last = datetime.fromtimestamp(history[-1]["timestamp"])
            days = (last - first).days + 1
            
            attrs.update({
                "first_cycle": first.isoformat(),
                "last_cycle": last.isoformat(),
                "days_running": days,
                "avg_cycles_per_day": round(total / days, 1) if days > 0 else 0,
            })
        
        return attrs


class TrvDiagnosticsSensor(TrvBaseSensor):
    """Diagnostický sensor pro místnost."""

    def __init__(self, coordinator, room_name: str, entry_id: str):
        """Inicializace diagnostic senzoru."""
        super().__init__(coordinator, room_name, entry_id, "diagnostics")
        self._attr_name = f"TRV {room_name} Diagnostics"
        self._attr_icon = "mdi:stethoscope"
        self._attr_entity_category = "diagnostic"

    @property
    def native_value(self):
        """Vrací celkový stav (healthy/warning/error)."""
        room = self.coordinator.room
        
        # Zkontrolovat dostupnost komponent
        temp_state = room._hass.states.get(room._temperature_entity)
        target_state = room._hass.states.get(room._target_entity)
        
        if not temp_state or temp_state.state in ("unknown", "unavailable"):
            return "error"
        if not target_state or target_state.state in ("unknown", "unavailable"):
            return "error"
        
        # Zkontrolovat TRV
        for trv in room._trv_entities:
            trv_state = room._hass.states.get(trv["entity"])
            if not trv_state or trv_state.state in ("unknown", "unavailable"):
                if trv.get("enabled", True):
                    return "error"
        
        # Zkontrolovat warnings
        history = room.history
        if history:
            recent_invalid = sum(1 for c in history[-10:] if not c.get("valid", True))
            if recent_invalid > 5:
                return "warning"
        
        return "healthy"

    @property
    def extra_state_attributes(self):
        """Vrací diagnostické atributy."""
        room = self.coordinator.room
        hass = room._hass
        
        # === Stav komponent ===
        components = {}
        
        # Temperature sensor
        temp_state = hass.states.get(room._temperature_entity)
        if temp_state:
            components["temperature_sensor"] = {
                "entity_id": room._temperature_entity,
                "state": temp_state.state,
                "status": "online" if temp_state.state not in ("unknown", "unavailable") else "offline",
                "last_update": temp_state.last_updated.isoformat() if temp_state.last_updated else None,
            }
        
        # Target sensor
        target_state = hass.states.get(room._target_entity)
        if target_state:
            components["target_sensor"] = {
                "entity_id": room._target_entity,
                "state": target_state.state,
                "status": "online" if target_state.state not in ("unknown", "unavailable") else "offline",
                "last_update": target_state.last_updated.isoformat() if target_state.last_updated else None,
            }
        
        # Window sensors
        if room._window_entities:
            window_data = []
            for window_entity in room._window_entities:
                window_state = hass.states.get(window_entity)
                if window_state:
                    window_data.append({
                        "entity_id": window_entity,
                        "state": window_state.state,
                        "status": "online" if window_state.state not in ("unknown", "unavailable") else "offline",
                        "last_update": window_state.last_updated.isoformat() if window_state.last_updated else None,
                    })
            if window_data:
                components["window_sensors"] = window_data
        
        # TRV devices
        trv_data = []
        for trv in room._trv_entities:
            trv_state = hass.states.get(trv["entity"])
            if trv_state:
                trv_data.append({
                    "entity_id": trv["entity"],
                    "state": trv_state.state,
                    "current_temp": trv_state.attributes.get("current_temperature"),
                    "status": "online" if trv_state.state not in ("unknown", "unavailable") else "offline",
                    "enabled": trv.get("enabled", True),
                })
        components["trv_devices"] = trv_data
        
        # === Invalidace cyklů ===
        history = room.history
        invalid_cycles = [c for c in history if not c.get("valid", True)]
        
        invalidation_reasons = {}
        for cycle in invalid_cycles:
            reason = cycle.get("invalidation_reason", "unknown")
            invalidation_reasons[reason] = invalidation_reasons.get(reason, 0) + 1
        
        # POST-VENT cykly (jsou validní, ale nepoužité pro učení)
        post_vent_count = sum(1 for c in history if c.get("post_vent", False))
        
        cycle_invalidations = {
            "total_invalid_cycles": len(invalid_cycles),
            "reasons": invalidation_reasons,
            "post_vent_cycles": post_vent_count,
        }
        
        # === Konfigurace ===
        config = {
            "hysteresis": room._hysteresis,
            "window_open_delay": room._window_open_delay,
            "max_heating_duration": room._max_heating_duration,
            "learning_cycles_required": room._learning_cycles_required,
        }
        
        return {
            "components": components,
            "cycle_invalidations": cycle_invalidations,
            "config": config,
            "current_state": room.state,
        }


class TrvSummarySensor(SensorEntity):
    """Summary sensor pro všechny místnosti."""

    def __init__(self, hass, entry_ids):
        """Inicializace summary senzoru."""
        self._hass = hass
        self._entry_ids = entry_ids
        self._attr_unique_id = f"{DOMAIN}_summary"
        self._attr_name = "TRV Regulator Summary"
        self._attr_icon = "mdi:home-thermometer-outline"
        self._attr_has_entity_name = True
    
    @property
    def device_info(self):
        """Informace o zařízení."""
        return {
            "identifiers": {(DOMAIN, "summary")},
            "name": "TRV Regulator Summary",
            "manufacturer": "Custom",
            "model": "TRV Regulator Summary",
            "via_device": None,
        }

    @property
    def native_value(self):
        """Počet místností."""
        return f"{len(self._entry_ids)} rooms"

    @property
    def extra_state_attributes(self):
        """Agregované atributy ze všech místností."""
        rooms_data = []
        total_cycles = 0
        rooms_learned = 0
        rooms_learning = 0
        
        for entry_id in self._entry_ids:
            coordinator = self._hass.data[DOMAIN].get(entry_id)
            if not coordinator:
                continue
                
            room = coordinator.room
            room_name = room._room_name
            is_learning = room.is_learning
            valid_cycles = room.valid_cycles_count
            avg_duration = room.avg_heating_duration
            
            rooms_data.append({
                "name": room_name,
                "state": "learning" if is_learning else "learned",
                "valid_cycles": valid_cycles,
                "avg_heating_time": int(avg_duration) if avg_duration else None,
            })
            
            total_cycles += len(room.history)
            if is_learning:
                rooms_learning += 1
            else:
                rooms_learned += 1
        
        return {
            "rooms": rooms_data,
            "total_cycles": total_cycles,
            "rooms_learned": rooms_learned,
            "rooms_learning": rooms_learning,
        }

    async def async_update(self):
        """Update je handled automaticky přes coordinatory."""
        pass
