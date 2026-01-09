"""Coordinator pro TRV Regulator."""
from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class TrvRegulatorCoordinator(DataUpdateCoordinator):
    """Coordinator pro synchronizaci s Home Assistant."""

    def __init__(self, hass, room_controller):
        """Inicializace coordinatoru."""
        super().__init__(
            hass,
            _LOGGER,
            name="TRV Regulator",
            update_interval=timedelta(seconds=30),  # fallback
        )
        self.room = room_controller

    async def _async_update_data(self):
        """Volá se periodicky + při změně tracked entit."""
        await self.room.async_update()
        return {"state": self.room.state}
