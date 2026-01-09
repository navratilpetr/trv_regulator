"""Stavový automat pro řízení TRV v místnosti."""
import logging
import time
from typing import Any

from .const import (
    STATE_IDLE,
    STATE_HEATING,
    STATE_VENT,
    STATE_POST_VENT,
    TRV_ON,
    TRV_OFF,
)

_LOGGER = logging.getLogger(__name__)


class RoomController:
    """Stavový automat pro jednu místnost."""

    def __init__(
        self,
        hass,
        room_name: str,
        temperature_entity: str,
        target_entity: str,
        trv_entities: list[dict],
        window_entities: list[str],
        door_entities: list[str],
        heating_water_temp_entity: str,
        hysteresis: float,
        vent_delay: int,
        post_vent_duration: int,
    ):
        """Inicializace controlleru."""
        self._hass = hass
        self._room_name = room_name
        self._temperature_entity = temperature_entity
        self._target_entity = target_entity
        self._trv_entities = trv_entities
        self._window_entities = window_entities
        self._door_entities = door_entities
        self._heating_water_temp_entity = heating_water_temp_entity
        self._hysteresis = hysteresis
        self._vent_delay = vent_delay
        self._post_vent_duration = post_vent_duration

        self._state = STATE_IDLE
        self._window_opened_at = None
        self._post_vent_timer = None

        _LOGGER.info(
            f"TRV [{self._room_name}] initialized: "
            f"hysteresis={self._hysteresis}°C, "
            f"vent_delay={self._vent_delay}s, "
            f"post_vent_duration={self._post_vent_duration}s"
        )

    async def async_update(self):
        """Hlavní update loop – volá se při změně libovolné entity."""
        # 1. Načti aktuální hodnoty
        temp = self._get_temperature()
        target = self._get_target()
        window_open = self._any_window_open()

        # 2. Vyhodnoť stavový automat
        new_state = self._evaluate_state(temp, target, window_open)

        # 3. Pokud se stav změnil → přejdi
        if new_state != self._state:
            await self._transition_to(new_state, temp, target)

    def _evaluate_state(self, temp: float, target: float, window_open: bool) -> str:
        """Deterministická logika přechodů."""
        # VENT má přednost
        if window_open:
            if self._window_opened_at is None:
                self._window_opened_at = time.time()
                _LOGGER.info(f"TRV [{self._room_name}]: Window opened")

            elapsed = time.time() - self._window_opened_at
            if elapsed >= self._vent_delay:
                _LOGGER.debug(
                    f"TRV [{self._room_name}]: Window open for {elapsed:.0f}s "
                    f"(>= {self._vent_delay}s) → triggering VENT"
                )
                return STATE_VENT
        else:
            if self._window_opened_at is not None:
                _LOGGER.info(f"TRV [{self._room_name}]: Window closed")
            self._window_opened_at = None

        # POST_VENT nesmí skončit dřív než timer
        if self._state == STATE_POST_VENT:
            if self._post_vent_timer and not self._post_vent_timer_expired():
                elapsed = time.time() - self._post_vent_timer
                remaining = self._post_vent_duration - elapsed
                _LOGGER.debug(
                    f"TRV [{self._room_name}]: POST_VENT timer: "
                    f"{elapsed:.0f}s elapsed, {remaining:.0f}s remaining"
                )
                return STATE_POST_VENT
            else:
                _LOGGER.info(
                    f"TRV [{self._room_name}]: POST_VENT timer expired "
                    f"({self._post_vent_duration}s) → evaluating heating"
                )
                # Timer vypršel → okamžitě vyhodnotit regulaci
                return self._evaluate_heating(temp, target)

        # Během VENT ignoruj teplotu
        if self._state == STATE_VENT:
            if not window_open:
                return STATE_POST_VENT
            return STATE_VENT

        # Regulace (pouze IDLE/HEATING)
        return self._evaluate_heating(temp, target)

    def _evaluate_heating(self, temp: float, target: float) -> str:
        """Vyhodnotí, zda má být zapnuto topení."""
        lower_threshold = target - self._hysteresis
        upper_threshold = target + self._hysteresis

        if temp <= lower_threshold:
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Temperature {temp:.1f}°C "
                f"<= {lower_threshold:.1f}°C (target-hysteresis) → HEATING"
            )
            return STATE_HEATING
        elif temp >= upper_threshold:
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Temperature {temp:.1f}°C "
                f">= {upper_threshold:.1f}°C (target+hysteresis) → IDLE"
            )
            return STATE_IDLE

        _LOGGER.debug(
            f"TRV [{self._room_name}]: Temperature {temp:.1f}°C "
            f"within hysteresis ({lower_threshold:.1f}-{upper_threshold:.1f}°C) "
            f"→ staying in {self._state.upper()}"
        )
        return self._state  # Zůstat v aktuálním stavu

    async def _transition_to(self, new_state: str, temp: float, target: float):
        """Provede přechod do nového stavu."""
        old_state = self._state
        self._state = new_state

        # Log
        _LOGGER.info(
            f"TRV [{self._room_name}]: {old_state.upper()} → {new_state.upper()} "
            f"(temp={temp:.1f}°C, target={target:.1f}°C, "
            f"hysteresis=±{self._hysteresis}°C)"
        )

        # Akce podle nového stavu
        if new_state == STATE_HEATING:
            await self._set_all_trv(TRV_ON)

        elif new_state == STATE_IDLE:
            await self._set_all_trv(TRV_OFF)

        elif new_state == STATE_VENT:
            await self._set_all_trv(TRV_OFF)

        elif new_state == STATE_POST_VENT:
            # TRV už jsou OFF ze stavu VENT
            self._start_post_vent_timer()

    async def _set_all_trv(self, command: dict[str, Any]):
        """Nastaví všechny aktivní TRV (respektuje enable/disable)."""
        mode = command["hvac_mode"]
        temp = command["temperature"]

        active_count = sum(1 for trv in self._trv_entities if trv.get("enabled", True))

        _LOGGER.info(
            f"TRV [{self._room_name}]: Setting {active_count} TRV(s) to "
            f"{mode.upper()} ({temp}°C)"
        )

        for trv_config in self._trv_entities:
            if not trv_config.get("enabled", True):
                continue

            entity_id = trv_config["entity"]

            _LOGGER.debug(
                f"TRV [{self._room_name}]: Sending to {entity_id}: "
                f"hvac_mode={mode}, temperature={temp}"
            )

            # Nastavit hvac_mode
            await self._hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {"entity_id": entity_id, "hvac_mode": mode},
                blocking=True,
            )

            # Nastavit temperature
            await self._hass.services.async_call(
                "climate",
                "set_temperature",
                {"entity_id": entity_id, "temperature": temp},
                blocking=True,
            )

    def _get_temperature(self) -> float:
        """Načte aktuální teplotu."""
        state = self._hass.states.get(self._temperature_entity)
        if state is None or state.state in ("unknown", "unavailable"):
            _LOGGER.warning(
                f"TRV [{self._room_name}]: Temperature entity "
                f"{self._temperature_entity} unavailable"
            )
            return 0.0
        try:
            return float(state.state)
        except (ValueError, TypeError):
            _LOGGER.error(
                f"TRV [{self._room_name}]: Cannot parse temperature: {state.state}"
            )
            return 0.0

    def _get_target(self) -> float:
        """Načte cílovou teplotu."""
        state = self._hass.states.get(self._target_entity)
        if state is None or state.state in ("unknown", "unavailable"):
            _LOGGER.warning(
                f"TRV [{self._room_name}]: Target entity "
                f"{self._target_entity} unavailable, using default 20.0"
            )
            return 20.0
        try:
            return float(state.state)
        except (ValueError, TypeError):
            _LOGGER.error(
                f"TRV [{self._room_name}]: Cannot parse target: {state.state}"
            )
            return 20.0

    def _any_window_open(self) -> bool:
        """Kontroluje, zda je nějaké okno otevřené."""
        for entity_id in self._window_entities:
            state = self._hass.states.get(entity_id)
            if state and state.state == "on":
                return True
        return False

    def _start_post_vent_timer(self):
        """Spustí POST_VENT timer."""
        self._post_vent_timer = time.time()

    def _post_vent_timer_expired(self) -> bool:
        """Zkontroluje, zda vypršel POST_VENT timer."""
        if not self._post_vent_timer:
            return True
        return time.time() - self._post_vent_timer >= self._post_vent_duration

    @property
    def state(self) -> str:
        """Vrací aktuální stav."""
        return self._state
