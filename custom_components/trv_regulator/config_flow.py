"""Config flow pro TRV Regulator."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    DEFAULT_HYSTERESIS,
    DEFAULT_VENT_DELAY,
    DEFAULT_POST_VENT_DURATION,
)


class TrvRegulatorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pro TRV Regulator."""

    VERSION = 1

    def __init__(self):
        """Inicializace config flow."""
        self._data = {}

    async def async_step_user(self, user_input=None):
        """Krok 1: Základní informace."""
        if user_input is not None:
            self._data = user_input
            return await self.async_step_entities()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("room_name"): str,
                }
            ),
        )

    async def async_step_entities(self, user_input=None):
        """Krok 2: Povinné entity."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_optional()

        return self.async_show_form(
            step_id="entities",
            data_schema=vol.Schema(
                {
                    vol.Required("temperature_entity"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required("target_entity"): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=["input_number", "number", "climate"]
                        )
                    ),
                    vol.Required("trv_entities"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="climate", multiple=True)
                    ),
                    vol.Required("heating_water_temp_entity"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                }
            ),
        )

    async def async_step_optional(self, user_input=None):
        """Krok 3: Volitelné entity a parametry."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title=self._data["room_name"],
                data=self._data,
            )

        return self.async_show_form(
            step_id="optional",
            data_schema=vol.Schema(
                {
                    vol.Optional("window_entities", default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="binary_sensor", multiple=True
                        )
                    ),
                    vol.Optional("door_entities", default=[]): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="binary_sensor", multiple=True
                        )
                    ),
                    vol.Optional(
                        "hysteresis", default=DEFAULT_HYSTERESIS
                    ): vol.Coerce(float),
                    vol.Optional("vent_delay", default=DEFAULT_VENT_DELAY): vol.Coerce(
                        int
                    ),
                    vol.Optional(
                        "post_vent_duration", default=DEFAULT_POST_VENT_DURATION
                    ): vol.Coerce(int),
                }
            ),
        )
