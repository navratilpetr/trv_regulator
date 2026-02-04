"""Per-TRV reliability sensors."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TrvIndividualReliabilitySensor(CoordinatorEntity, SensorEntity):
    """Individual TRV reliability sensor."""

    def __init__(self, coordinator, room_name: str, trv_entity_id: str, entry_id: str):
        """Initialize per-TRV reliability sensor."""
        super().__init__(coordinator)
        self._room_name = room_name
        self._trv_entity_id = trv_entity_id
        self._entry_id = entry_id
        
        # Extract TRV name from entity_id for a cleaner unique_id
        # e.g., "climate.trv_loznice_1" -> "trv_loznice_1"
        trv_name = trv_entity_id.split(".")[-1]
        
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_reliability_{trv_name}"
        self._attr_name = f"{trv_name.replace('_', ' ').title()} Reliability"
        self._attr_icon = "mdi:signal-variant"
        self._attr_has_entity_name = False  # Use full name

    @property
    def device_info(self):
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"TRV Regulator {self._room_name}",
            "manufacturer": "Custom",
            "model": "TRV Regulator",
            "via_device": None,
        }

    @property
    def native_value(self):
        """Return signal quality for this specific TRV."""
        try:
            metrics = self.coordinator.room._reliability_tracker.get_metrics()
            trv_stats = metrics.get("trv_statistics", {})
            
            if self._trv_entity_id in trv_stats:
                return trv_stats[self._trv_entity_id].get("signal_quality", "unknown")
            
            return "unknown"
        except Exception as e:
            _LOGGER.error(
                f"TRV [{self._room_name}]: Error getting reliability for {self._trv_entity_id}: {e}"
            )
            return "unknown"

    @property
    def extra_state_attributes(self):
        """Return per-TRV statistics."""
        try:
            metrics = self.coordinator.room._reliability_tracker.get_metrics()
            trv_stats = metrics.get("trv_statistics", {})
            
            if self._trv_entity_id in trv_stats:
                return trv_stats[self._trv_entity_id]
            
            return {
                "commands_sent": 0,
                "commands_failed": 0,
                "success_rate": 0.0,
                "signal_quality": "unknown",
                "last_seen": None,
            }
        except Exception as e:
            _LOGGER.error(
                f"TRV [{self._room_name}]: Error getting reliability attributes for {self._trv_entity_id}: {e}"
            )
            return {}
