"""Coordinator pro TRV Regulator."""
from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DEFAULT_UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class TrvRegulatorCoordinator(DataUpdateCoordinator):
    """Coordinator pro synchronizaci s Home Assistant."""

    def __init__(self, hass, room_controller):
        """Inicializace coordinatoru."""
        super().__init__(
            hass,
            _LOGGER,
            name="TRV Regulator",
            update_interval=timedelta(seconds=DEFAULT_UPDATE_INTERVAL),
        )
        self.room = room_controller

    async def _async_update_data(self):
        """Volá se periodicky + při změně tracked entit."""
        try:
            await self.room.async_update()
            
            # NELOGOVAT každý update (zbytečný spam)
            # Důležité věci se logují v room_controller.py
            
            return {"state": self.room.state}
        except Exception as err:
            # Chyby ANO logovat
            _LOGGER.error(f"Error fetching TRV Regulator data: {err}")
            raise
