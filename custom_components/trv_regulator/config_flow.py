"""Config flow pro TRV Regulator."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    DEFAULT_HYSTERESIS,
    DEFAULT_WINDOW_OPEN_DELAY,
    DEFAULT_LEARNING_SPEED,
    DEFAULT_LEARNING_CYCLES,
    DEFAULT_DESIRED_OVERSHOOT,
    DEFAULT_MIN_HEATING_DURATION,
    DEFAULT_MAX_HEATING_DURATION,
    DEFAULT_MAX_VALID_OVERSHOOT,
    DEFAULT_COOLDOWN_DURATION,
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
                            domain=["input_number", "number", "climate", "sensor"]
                        )
                    ),
                    vol.Required("trv_entities"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="climate", multiple=True)
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
                    vol.Optional(
                        "hysteresis", default=DEFAULT_HYSTERESIS
                    ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
                    vol.Optional("window_open_delay", default=DEFAULT_WINDOW_OPEN_DELAY): vol.All(
                        vol.Coerce(int), vol.Range(min=30, max=600)
                    ),
                    vol.Optional(
                        "learning_speed", default=DEFAULT_LEARNING_SPEED
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["conservative", "aggressive"],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        "learning_cycles_required", default=DEFAULT_LEARNING_CYCLES
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=30)),
                    vol.Optional(
                        "desired_overshoot", default=DEFAULT_DESIRED_OVERSHOOT
                    ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=0.5)),
                    vol.Optional(
                        "min_heating_duration", default=DEFAULT_MIN_HEATING_DURATION
                    ): vol.All(vol.Coerce(int), vol.Range(min=60, max=600)),
                    vol.Optional(
                        "max_heating_duration", default=DEFAULT_MAX_HEATING_DURATION
                    ): vol.All(vol.Coerce(int), vol.Range(min=900, max=10800)),
                    vol.Optional(
                        "max_valid_overshoot", default=DEFAULT_MAX_VALID_OVERSHOOT
                    ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=5.0)),
                    vol.Optional(
                        "cooldown_duration", default=DEFAULT_COOLDOWN_DURATION
                    ): vol.All(vol.Coerce(int), vol.Range(min=600, max=1800)),
                }
            ),
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        """Získat options flow pro úpravu konfigurace."""
        return TrvRegulatorOptionsFlow()


class TrvRegulatorOptionsFlow(config_entries.OptionsFlow):
    """Options flow pro úpravu konfigurace TRV Regulator."""

    async def async_step_init(self, user_input=None):
        """Zobrazit formulář pro úpravu parametrů."""
        if user_input is not None:
            # Uložit do options (správný způsob)
            return self.async_create_entry(title="", data=user_input)

        # Načíst aktuální hodnoty z options nebo fallback na data
        current_options = self.config_entry.options
        current_data = self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "window_entities",
                        default=current_options.get("window_entities", current_data.get("window_entities", []))
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="binary_sensor", multiple=True
                        )
                    ),
                    vol.Optional(
                        "hysteresis",
                        default=current_options.get("hysteresis", current_data.get("hysteresis", DEFAULT_HYSTERESIS))
                    ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=2.0)),
                    vol.Optional(
                        "window_open_delay",
                        default=current_options.get("window_open_delay", current_data.get("window_open_delay", DEFAULT_WINDOW_OPEN_DELAY))
                    ): vol.All(vol.Coerce(int), vol.Range(min=30, max=600)),
                    vol.Optional(
                        "learning_speed",
                        default=current_options.get("learning_speed", current_data.get("learning_speed", DEFAULT_LEARNING_SPEED))
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["conservative", "aggressive"],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        "learning_cycles_required",
                        default=current_options.get("learning_cycles_required", current_data.get("learning_cycles_required", DEFAULT_LEARNING_CYCLES))
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=30)),
                    vol.Optional(
                        "desired_overshoot",
                        default=current_options.get("desired_overshoot", current_data.get("desired_overshoot", DEFAULT_DESIRED_OVERSHOOT))
                    ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=0.5)),
                    vol.Optional(
                        "min_heating_duration",
                        default=current_options.get("min_heating_duration", current_data.get("min_heating_duration", DEFAULT_MIN_HEATING_DURATION))
                    ): vol.All(vol.Coerce(int), vol.Range(min=60, max=600)),
                    vol.Optional(
                        "max_heating_duration",
                        default=current_options.get("max_heating_duration", current_data.get("max_heating_duration", DEFAULT_MAX_HEATING_DURATION))
                    ): vol.All(vol.Coerce(int), vol.Range(min=900, max=10800)),
                    vol.Optional(
                        "max_valid_overshoot",
                        default=current_options.get("max_valid_overshoot", current_data.get("max_valid_overshoot", DEFAULT_MAX_VALID_OVERSHOOT))
                    ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=5.0)),
                    vol.Optional(
                        "cooldown_duration",
                        default=current_options.get("cooldown_duration", current_data.get("cooldown_duration", DEFAULT_COOLDOWN_DURATION))
                    ): vol.All(vol.Coerce(int), vol.Range(min=600, max=1800)),
                }
            ),
        )
