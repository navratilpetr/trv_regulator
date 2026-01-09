"""Stavový automat pro řízení TRV v místnosti."""
import logging
import time
from typing import Any
from collections import deque

from .const import (
    STATE_IDLE,
    STATE_HEATING,
    STATE_VENT,
    STATE_POST_VENT,
    TRV_ON,
    TRV_OFF,
    DEFAULT_GAIN,
    DEFAULT_OFFSET,
    TRV_MIN_TEMP,
    TRV_MAX_TEMP,
    DEFAULT_ADAPTIVE_LEARNING,
    DEFAULT_UPDATE_INTERVAL,
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
        gain: float = DEFAULT_GAIN,
        offset: float = DEFAULT_OFFSET,
        adaptive_learning: bool = DEFAULT_ADAPTIVE_LEARNING,
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
        self._gain = gain
        self._offset = offset
        self._adaptive_learning = adaptive_learning

        self._state = STATE_IDLE
        self._window_opened_at = None
        self._post_vent_timer = None
        
        # Adaptivní učení - historie teplot
        # 1 hodina při DEFAULT_UPDATE_INTERVAL (10s) = 360 vzorků
        history_size = 60 * 60 // DEFAULT_UPDATE_INTERVAL
        self._temp_history = deque(maxlen=history_size)
        self._last_trv_target = None
        self._commands_total = 0

        _LOGGER.info(
            f"TRV [{self._room_name}] initialized: "
            f"hysteresis={self._hysteresis}°C, "
            f"gain={self._gain}, offset={self._offset}, "
            f"vent_delay={self._vent_delay}s, "
            f"post_vent_duration={self._post_vent_duration}s, "
            f"adaptive_learning={self._adaptive_learning}"
        )

    async def async_update(self):
        """Hlavní update loop – volá se při změně libovolné entity."""
        # 1. Načti aktuální hodnoty
        temp = self._get_temperature()
        target = self._get_target()
        window_open = self._any_window_open()
        
        # Uložit do historie pro adaptivní učení
        self._temp_history.append(temp)

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
        """Vyhodnotí, zda má být zapnuto topení (s hysterezí pro změnu stavu)."""
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
    
    def _calculate_proportional_target(
        self, room_temp: float, desired_temp: float, trv_local_temp: float
    ) -> float:
        """
        Vypočítá cílovou teplotu pro TRV pomocí proporcionální regulace.
        
        Args:
            room_temp: Teplota v místnosti (externím senzorem)
            desired_temp: Požadovaná teplota
            trv_local_temp: Lokální teplota z TRV hlavice
        
        Returns:
            Cílová teplota pro nastavení TRV (5-35°C)
        """
        # Sanity check vstupních hodnot
        if not (-10 <= room_temp <= 50) or not (-10 <= desired_temp <= 50):
            _LOGGER.warning(
                f"TRV [{self._room_name}]: Invalid temperature values "
                f"(room={room_temp}°C, desired={desired_temp}°C), "
                f"using safe default"
            )
            return TRV_MIN_TEMP
        
        diff = desired_temp - room_temp
        
        # Proporcionální zesílení
        target = diff * self._gain + self._offset + trv_local_temp
        
        # Clamp 5-35°C
        clamped = max(TRV_MIN_TEMP, min(TRV_MAX_TEMP, target))
        
        _LOGGER.debug(
            f"TRV [{self._room_name}]: Proportional calculation: "
            f"diff={diff:.2f}°C, gain={self._gain}, offset={self._offset}, "
            f"trv_local={trv_local_temp:.1f}°C → "
            f"target={target:.1f}°C (clamped to {clamped:.1f}°C)"
        )
        
        return clamped

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
            await self._set_all_trv_proportional(temp, target)

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

            # Nastavit hvac_mode a temperature v jednom volání
            await self._hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": entity_id,
                    "hvac_mode": mode,
                    "temperature": round(temp, 1)
                },
                blocking=True,
            )
        
        self._commands_total += active_count
        
    async def _set_all_trv_proportional(self, room_temp: float, desired_temp: float):
        """Nastaví všechny TRV pomocí proporcionální regulace."""
        active_trvs = [trv for trv in self._trv_entities if trv.get("enabled", True)]
        active_count = len(active_trvs)
        
        if active_count == 0:
            _LOGGER.warning(f"TRV [{self._room_name}]: No active TRVs to control")
            return
        
        # Použít první TRV pro získání lokální teploty (všechny by měly být podobné)
        first_trv = active_trvs[0]["entity"]
        trv_local_temp = self._get_trv_local_temperature(first_trv)
        
        # Vypočítat cílovou teplotu
        target_temp = self._calculate_proportional_target(
            room_temp, desired_temp, trv_local_temp
        )
        
        self._last_trv_target = target_temp
        
        _LOGGER.info(
            f"TRV [{self._room_name}]: Setting {active_count} TRV(s) to "
            f"HEAT mode with proportional target={target_temp:.1f}°C "
            f"(room={room_temp:.1f}°C, desired={desired_temp:.1f}°C, "
            f"trv_local={trv_local_temp:.1f}°C)"
        )
        
        for trv_config in active_trvs:
            entity_id = trv_config["entity"]
            
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Sending to {entity_id}: "
                f"hvac_mode=heat, temperature={target_temp:.1f}°C"
            )
            
            # Nastavit hvac_mode a proporcionální teplotu v jednom volání
            await self._hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": entity_id,
                    "hvac_mode": "heat",
                    "temperature": round(target_temp, 1)
                },
                blocking=True,
            )
        
        self._commands_total += active_count

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
    
    def _get_trv_local_temperature(self, entity_id: str) -> float:
        """
        Načte lokální teplotu z TRV hlavice.
        
        Args:
            entity_id: ID entity TRV hlavice
        
        Returns:
            Lokální teplota měřená TRV hlavicí
        """
        state = self._hass.states.get(entity_id)
        if state is None:
            _LOGGER.warning(
                f"TRV [{self._room_name}]: TRV entity {entity_id} not found"
            )
            # Fallback na pokojovou teplotu
            return self._get_temperature()
        
        # Zkusit získat current_temperature z atributů
        trv_temp = state.attributes.get("current_temperature")
        
        if trv_temp is None:
            _LOGGER.debug(
                f"TRV [{self._room_name}]: TRV {entity_id} has no current_temperature, "
                f"using room temperature as fallback"
            )
            return self._get_temperature()
        
        try:
            temp = float(trv_temp)
            _LOGGER.debug(
                f"TRV [{self._room_name}]: TRV local temperature from {entity_id}: {temp:.1f}°C"
            )
            return temp
        except (ValueError, TypeError):
            _LOGGER.error(
                f"TRV [{self._room_name}]: Cannot parse TRV temperature: {trv_temp}"
            )
            return self._get_temperature()

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
    
    def calculate_oscillation(self) -> float:
        """
        Vypočítá oscilaci teploty za poslední hodinu.
        
        Returns:
            Poloviční rozpětí teplot (amplituda oscilace) v °C
        """
        # Minimálně 1 minuta dat při DEFAULT_UPDATE_INTERVAL (10s) = 6 vzorků
        min_samples = 60 // DEFAULT_UPDATE_INTERVAL
        if len(self._temp_history) < min_samples:
            return 0.0
        
        recent_temps = list(self._temp_history)
        oscillation = (max(recent_temps) - min(recent_temps)) / 2
        
        _LOGGER.debug(
            f"TRV [{self._room_name}]: Oscillation over {len(recent_temps)} samples: "
            f"{oscillation:.2f}°C"
        )
        
        return oscillation
    
    def get_learned_gain(self) -> float | None:
        """
        Vrací naučený gain (placeholder pro budoucí ML).
        
        Returns:
            Optimální gain nebo None pokud ještě není naučen
        """
        # TODO: Implementovat ML algoritmus
        # Pro teď vracíme None - použije se aktuální gain
        return None
    
    def recommend_gain_adjustment(self) -> float | None:
        """
        Doporučí úpravu gain na základě oscilací (placeholder pro budoucí ML).
        
        Returns:
            Doporučený nový gain nebo None pokud není doporučení
        """
        if not self._adaptive_learning:
            return None
        
        osc = self.calculate_oscillation()
        
        # Minimálně 30 minut dat pro doporučení (při DEFAULT_UPDATE_INTERVAL)
        min_samples_for_recommendation = 30 * 60 // DEFAULT_UPDATE_INTERVAL
        
        # Velmi jednoduchá heuristika - bude nahrazena ML
        if osc > 0.4:  # Příliš velké oscilace
            new_gain = self._gain * 0.9
            _LOGGER.info(
                f"TRV [{self._room_name}]: High oscillation ({osc:.2f}°C), "
                f"recommending gain reduction: {self._gain:.1f} → {new_gain:.1f}"
            )
            return new_gain
        elif osc < 0.2 and len(self._temp_history) >= min_samples_for_recommendation:
            new_gain = self._gain * 1.05
            _LOGGER.info(
                f"TRV [{self._room_name}]: Low oscillation ({osc:.2f}°C), "
                f"recommending gain increase: {self._gain:.1f} → {new_gain:.1f}"
            )
            return new_gain
        
        return None

    @property
    def state(self) -> str:
        """Vrací aktuální stav."""
        return self._state
    
    @property
    def gain(self) -> float:
        """Vrací aktuální gain."""
        return self._gain
    
    @property
    def offset(self) -> float:
        """Vrací aktuální offset."""
        return self._offset
    
    @property
    def last_trv_target(self) -> float | None:
        """Vrací poslední vypočítanou cílovou teplotu pro TRV."""
        return self._last_trv_target
    
    @property
    def commands_total(self) -> int:
        """Vrací celkový počet odeslaných příkazů."""
        return self._commands_total
