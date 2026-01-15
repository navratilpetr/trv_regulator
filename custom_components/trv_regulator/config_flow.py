"""Config flow pro TRV Regulator."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    DEFAULT_HYSTERESIS,
    DEFAULT_WINDOW_OPEN_DELAY,
    DEFAULT_LEARNING_CYCLES,
    DEFAULT_DESIRED_OVERSHOOT,
    DEFAULT_MIN_HEATING_DURATION,
    DEFAULT_MAX_HEATING_DURATION,
    DEFAULT_MAX_VALID_OVERSHOOT,
    DEFAULT_COOLDOWN_DURATION,
)


class TrvRegulatorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow pro TRV Regulator."""

    VERSION = 2

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
        errors = {}
        
        if user_input is not None:
            # Zpracovat změny TRV enabled/disabled
            trv_entities = self.config_entry.data.get("trv_entities", [])
            enabled_trv_ids = user_input.get("enabled_trv_entities", [])
            
            # Validace - minimálně jedna TRV musí být aktivní
            if not enabled_trv_ids:
                errors["base"] = "at_least_one_trv_required"
            else:
                # Rekonstruovat trv_entities s novým enabled stavem
                # Zachovat formát - pokud jsou již ve formátu dict, použít to, jinak vytvořit dict
                new_trv_entities = []
                for trv in trv_entities:
                    # Zjistit entity_id - může být string nebo dict
                    if isinstance(trv, dict):
                        entity_id = trv["entity"]
                    else:
                        entity_id = trv
                    
                    new_trv_entities.append({
                        "entity": entity_id,
                        "enabled": entity_id in enabled_trv_ids
                    })
                
                # Aktualizovat config entry s novými daty
                new_data = {**self.config_entry.data, "trv_entities": new_trv_entities}
                
                # Uložit options (bez trv_entities, to je v data)
                new_options = {k: v for k, v in user_input.items() if k != "enabled_trv_entities"}
                
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                    options=new_options
                )
                
                # Reload entry pro aplikaci změn
                await self.hass.config_entries.async_reload(self.config_entry.entry_id)
                
                return self.async_create_entry(title="", data={})
        
        # Načíst aktuální TRV
        trv_entities = self.config_entry.data.get("trv_entities", [])
        
        # Vytvořit seznam všech TRV ID a aktuálně aktivních
        all_trv_ids = []
        enabled_trv_ids = []
        
        for trv in trv_entities:
            # Zjistit entity_id a enabled stav
            if isinstance(trv, dict):
                entity_id = trv["entity"]
                is_enabled = trv.get("enabled", True)
            else:
                entity_id = trv
                is_enabled = True
            
            all_trv_ids.append(entity_id)
            if is_enabled:
                enabled_trv_ids.append(entity_id)
        
        # Získat friendly names pro TRV
        trv_options = {}
        for trv_id in all_trv_ids:
            state = self.hass.states.get(trv_id)
            if state:
                trv_options[trv_id] = state.attributes.get("friendly_name", trv_id)
            else:
                trv_options[trv_id] = trv_id
        
        # Načíst aktuální hodnoty z options nebo fallback na data
        current_options = self.config_entry.options
        current_data = self.config_entry.data

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "enabled_trv_entities",
                        default=enabled_trv_ids,
                        description={"suggested_value": enabled_trv_ids}
                    ): cv.multi_select(trv_options),
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
            errors=errors,
        )
