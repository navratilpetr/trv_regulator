"""Stavový automat pro řízení TRV v místnosti."""
import logging
import time
import json
import os
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
    MIN_GAIN,
    MAX_GAIN,
    MIN_OFFSET,
    MAX_OFFSET,
    LEARNING_CYCLES_REQUIRED,
    MAX_GAIN_CHANGES_PER_HOUR,
    STORAGE_DIR,
    STORAGE_FILE,
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
        
        # Adaptivní učení - performance tracking
        self._performance_history = deque(maxlen=100)
        self._last_oscillation_log = 0
        self._learning_paused_until = None
        self._gain_changes_last_hour = deque(maxlen=10)
        self._last_overshoot = None
        
        # Načíst naučené parametry
        self._load_learned_params()

        _LOGGER.info(
            f"TRV [{self._room_name}] initialized: "
            f"hysteresis={self._hysteresis}°C, "
            f"gain={self._gain}, offset={self._offset}, "
            f"vent_delay={self._vent_delay}s, "
            f"post_vent_duration={self._post_vent_duration}s, "
            f"adaptive_learning={self._adaptive_learning}"
        )
        
        # Vytvořit senzory
        hass.loop.create_task(self._create_sensors())

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
        # 4. NOVÉ: Pokud je v HEATING, průběžně aktualizuj target
        elif new_state == STATE_HEATING:
            await self._update_proportional_target(temp, target)
        
        # 5. Aktualizovat senzory
        await self._update_sensors()

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
            # Logovat jen pokud se stav mění
            if self._state != STATE_HEATING:
                _LOGGER.debug(
                    f"TRV [{self._room_name}]: Temperature {temp:.1f}°C "
                    f"<= {lower_threshold:.1f}°C (target-hysteresis) → HEATING"
                )
            return STATE_HEATING
        elif temp >= upper_threshold:
            # Logovat jen pokud se stav mění
            if self._state != STATE_IDLE:
                _LOGGER.debug(
                    f"TRV [{self._room_name}]: Temperature {temp:.1f}°C "
                    f">= {upper_threshold:.1f}°C (target+hysteresis) → IDLE"
                )
            return STATE_IDLE

        # Zůstat v aktuálním stavu - nelogovat
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
            
            # Uložit performance data při přechodu HEATING → IDLE
            # (ignorujeme přechody z VENT/POST_VENT)
            if old_state == STATE_HEATING:
                await self._save_performance_data(temp, target)
                await self._check_and_apply_learning()

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
        
        # Logovat jen každou hodinu
        current_time = time.time()
        if current_time - self._last_oscillation_log >= 3600:
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Oscillation over {len(recent_temps)} samples: "
                f"{oscillation:.2f}°C"
            )
            self._last_oscillation_log = current_time
        
        return oscillation
    
    def get_learned_gain(self) -> float | None:
        """
        Vrací naučený gain (placeholder pro budoucí ML).
        
        Returns:
            Optimální gain nebo None pokud ještě není naučen
        """
        # Nahrazeno aktivním učením v _check_and_apply_learning
        return None
    
    def recommend_gain_adjustment(self) -> float | None:
        """
        Doporučí úpravu gain na základě oscilací (placeholder pro budoucí ML).
        
        Returns:
            Doporučený nový gain nebo None pokud není doporučení
        """
        # Nahrazeno aktivním učením v _check_and_apply_learning
        return None
    
    async def _update_proportional_target(self, room_temp: float, desired_temp: float):
        """Aktualizuje TRV target pokud se změnil (bez změny stavu)."""
        active_trvs = [trv for trv in self._trv_entities if trv.get("enabled", True)]
        
        if not active_trvs:
            return
        
        # Použít první TRV pro získání lokální teploty
        first_trv = active_trvs[0]["entity"]
        trv_local_temp = self._get_trv_local_temperature(first_trv)
        
        # Vypočítat nový target
        new_target = self._calculate_proportional_target(
            room_temp, desired_temp, trv_local_temp
        )
        
        # Poslat příkaz jen pokud se target změnil významně (> 0.05°C)
        if self._last_trv_target is None or abs(new_target - self._last_trv_target) > 0.05:
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Target changed during HEATING: "
                f"{self._last_trv_target:.1f}°C → {new_target:.1f}°C"
            )
            
            self._last_trv_target = new_target
            
            # Poslat nový target na všechny TRV
            for trv_config in active_trvs:
                entity_id = trv_config["entity"]
                
                await self._hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {
                        "entity_id": entity_id,
                        "hvac_mode": "heat",
                        "temperature": round(new_target, 1)
                    },
                    blocking=True,
                )
            
            self._commands_total += len(active_trvs)
    
    async def _save_performance_data(self, room_temp: float, target_temp: float):
        """Uloží data o topném cyklu."""
        overshoot = room_temp - target_temp
        oscillation = self.calculate_oscillation()
        
        performance_data = {
            "timestamp": time.time(),
            "room_temp": room_temp,
            "target_temp": target_temp,
            "overshoot": overshoot,
            "oscillation": oscillation,
            "gain": self._gain,
            "offset": self._offset,
        }
        
        self._performance_history.append(performance_data)
        self._last_overshoot = overshoot
        
        _LOGGER.debug(
            f"TRV [{self._room_name}]: Performance data saved - "
            f"overshoot={overshoot:.2f}°C, oscillation={oscillation:.2f}°C, "
            f"total_cycles={len(self._performance_history)}"
        )
    
    async def _check_and_apply_learning(self):
        """Zkontroluje zda je potřeba upravit gain/offset a aplikuje změny."""
        if not self._adaptive_learning:
            return
        
        # Potřebujeme alespoň LEARNING_CYCLES_REQUIRED cyklů
        if len(self._performance_history) < LEARNING_CYCLES_REQUIRED:
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Not enough cycles for learning "
                f"({len(self._performance_history)}/{LEARNING_CYCLES_REQUIRED})"
            )
            return
        
        # Kontrola zda není učení pozastaveno
        if self._learning_paused_until and time.time() < self._learning_paused_until:
            remaining = int(self._learning_paused_until - time.time())
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Learning paused for {remaining}s more"
            )
            return
        
        # Analyzovat posledních LEARNING_CYCLES_REQUIRED cyklů
        recent_cycles = list(self._performance_history)[-LEARNING_CYCLES_REQUIRED:]
        
        avg_overshoot = sum(c["overshoot"] for c in recent_cycles) / len(recent_cycles)
        avg_oscillation = sum(c["oscillation"] for c in recent_cycles) / len(recent_cycles)
        
        _LOGGER.info(
            f"TRV [{self._room_name}]: Learning analysis - "
            f"avg_overshoot={avg_overshoot:.2f}°C, avg_oscillation={avg_oscillation:.2f}°C"
        )
        
        new_gain = self._gain
        new_offset = self._offset
        adjustment_made = False
        
        # Velká oscilace (>0.5°C)
        if avg_oscillation > 0.5:
            new_gain = self._gain * 0.90
            adjustment_made = True
            _LOGGER.info(
                f"TRV [{self._room_name}]: High oscillation detected, reducing gain: "
                f"{self._gain:.1f} → {new_gain:.1f}"
            )
        # Přestřelování (avg overshoot > 0.4°C)
        elif avg_overshoot > 0.4:
            new_gain = self._gain * 0.95
            new_offset = self._offset - 0.1
            adjustment_made = True
            _LOGGER.info(
                f"TRV [{self._room_name}]: Overshooting detected, adjusting: "
                f"gain {self._gain:.1f} → {new_gain:.1f}, "
                f"offset {self._offset:.1f} → {new_offset:.1f}"
            )
        # Nedosahování cíle (avg overshoot < -0.4°C)
        elif avg_overshoot < -0.4:
            new_gain = self._gain * 1.05
            new_offset = self._offset + 0.1
            adjustment_made = True
            _LOGGER.info(
                f"TRV [{self._room_name}]: Undershooting detected, adjusting: "
                f"gain {self._gain:.1f} → {new_gain:.1f}, "
                f"offset {self._offset:.1f} → {new_offset:.1f}"
            )
        # Dobrá stabilita ale pomalá reakce
        elif avg_oscillation < 0.2 and abs(avg_overshoot) < 0.2:
            new_gain = self._gain * 1.02
            adjustment_made = True
            _LOGGER.info(
                f"TRV [{self._room_name}]: Good stability, slightly increasing gain: "
                f"{self._gain:.1f} → {new_gain:.1f}"
            )
        
        if adjustment_made:
            # Ochrana proti přeučení - kontrola počtu změn za poslední hodinu
            current_time = time.time()
            
            # Odstranit staré záznamy (starší než 1 hodina)
            while (self._gain_changes_last_hour and 
                   current_time - self._gain_changes_last_hour[0] > 3600):
                self._gain_changes_last_hour.popleft()
            
            # Kontrola limitu
            if len(self._gain_changes_last_hour) >= MAX_GAIN_CHANGES_PER_HOUR:
                _LOGGER.warning(
                    f"TRV [{self._room_name}]: Too many gain changes in last hour "
                    f"({len(self._gain_changes_last_hour)}), pausing learning for 1 hour"
                )
                self._learning_paused_until = current_time + 3600
                return
            
            # Clamp hodnoty do bezpečných limitů
            new_gain = max(MIN_GAIN, min(MAX_GAIN, new_gain))
            new_offset = max(MIN_OFFSET, min(MAX_OFFSET, new_offset))
            
            # Aplikovat změny
            self._gain = new_gain
            self._offset = new_offset
            
            # Zaznamenat změnu
            self._gain_changes_last_hour.append(current_time)
            
            # Uložit persistentně
            await self._save_learned_params()
            
            # Aktualizovat senzory
            await self._update_sensors()
            
            _LOGGER.info(
                f"TRV [{self._room_name}]: Applied new parameters - "
                f"gain={self._gain:.1f}, offset={self._offset:.2f}"
            )
    
    async def _save_learned_params(self):
        """Uloží naučené parametry do .storage/"""
        try:
            # Získat cestu k config
            config_path = self._hass.config.path()
            storage_path = os.path.join(config_path, STORAGE_DIR, STORAGE_FILE)
            
            # Načíst existující data
            data = {}
            if os.path.exists(storage_path):
                try:
                    with open(storage_path, "r") as f:
                        data = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    _LOGGER.warning(
                        f"TRV [{self._room_name}]: Could not read existing storage file: {e}"
                    )
            
            # Aktualizovat data pro tuto místnost
            data[self._room_name] = {
                "gain": self._gain,
                "offset": self._offset,
                "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "cycles_count": len(self._performance_history),
                "last_change_timestamp": int(time.time()),
            }
            
            # Vytvořit adresář pokud neexistuje
            os.makedirs(os.path.dirname(storage_path), exist_ok=True)
            
            # Uložit zpět
            with open(storage_path, "w") as f:
                json.dump(data, f, indent=2)
            
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Learned parameters saved to {storage_path}"
            )
            
        except Exception as e:
            _LOGGER.error(
                f"TRV [{self._room_name}]: Failed to save learned parameters: {e}"
            )
    
    def _load_learned_params(self):
        """Načte naučené parametry při startu."""
        try:
            config_path = self._hass.config.path()
            storage_path = os.path.join(config_path, STORAGE_DIR, STORAGE_FILE)
            
            if not os.path.exists(storage_path):
                _LOGGER.debug(
                    f"TRV [{self._room_name}]: No learned parameters file found"
                )
                return
            
            with open(storage_path, "r") as f:
                data = json.load(f)
            
            if self._room_name in data:
                room_data = data[self._room_name]
                self._gain = room_data.get("gain", self._gain)
                self._offset = room_data.get("offset", self._offset)
                
                _LOGGER.info(
                    f"TRV [{self._room_name}]: Loaded learned parameters - "
                    f"gain={self._gain:.1f}, offset={self._offset:.2f}, "
                    f"last_updated={room_data.get('last_updated', 'unknown')}"
                )
            else:
                _LOGGER.debug(
                    f"TRV [{self._room_name}]: No learned parameters for this room"
                )
                
        except Exception as e:
            _LOGGER.warning(
                f"TRV [{self._room_name}]: Could not load learned parameters: {e}"
            )
    
    async def _create_sensors(self):
        """Vytvoří senzory pro Home Assistant."""
        try:
            # Normalizovat jméno místnosti pro entity ID
            room_slug = self._room_name.lower().replace(" ", "_")
            
            sensors = {
                f"sensor.trv_{room_slug}_gain": {
                    "state": self._gain,
                    "attributes": {
                        "friendly_name": f"TRV {self._room_name} Gain",
                        "unit_of_measurement": None,
                        "icon": "mdi:tune",
                    },
                },
                f"sensor.trv_{room_slug}_offset": {
                    "state": self._offset,
                    "attributes": {
                        "friendly_name": f"TRV {self._room_name} Offset",
                        "unit_of_measurement": "°C",
                        "icon": "mdi:thermometer-lines",
                    },
                },
                f"sensor.trv_{room_slug}_oscillation": {
                    "state": 0.0,
                    "attributes": {
                        "friendly_name": f"TRV {self._room_name} Oscillation",
                        "unit_of_measurement": "°C",
                        "icon": "mdi:wave",
                    },
                },
                f"sensor.trv_{room_slug}_last_overshoot": {
                    "state": 0.0,
                    "attributes": {
                        "friendly_name": f"TRV {self._room_name} Last Overshoot",
                        "unit_of_measurement": "°C",
                        "icon": "mdi:arrow-up-down",
                    },
                },
                f"sensor.trv_{room_slug}_learning_cycles": {
                    "state": 0,
                    "attributes": {
                        "friendly_name": f"TRV {self._room_name} Learning Cycles",
                        "unit_of_measurement": "cycles",
                        "icon": "mdi:counter",
                    },
                },
                f"sensor.trv_{room_slug}_state": {
                    "state": self._state,
                    "attributes": {
                        "friendly_name": f"TRV {self._room_name} State",
                        "icon": "mdi:state-machine",
                    },
                },
                f"sensor.trv_{room_slug}_last_trv_target": {
                    "state": self._last_trv_target or 0.0,
                    "attributes": {
                        "friendly_name": f"TRV {self._room_name} Last TRV Target",
                        "unit_of_measurement": "°C",
                        "icon": "mdi:target",
                    },
                },
                f"sensor.trv_{room_slug}_commands_total": {
                    "state": self._commands_total,
                    "attributes": {
                        "friendly_name": f"TRV {self._room_name} Commands Total",
                        "unit_of_measurement": "commands",
                        "icon": "mdi:counter",
                    },
                },
            }
            
            for entity_id, sensor_data in sensors.items():
                self._hass.states.async_set(
                    entity_id,
                    sensor_data["state"],
                    sensor_data["attributes"]
                )
            
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Created {len(sensors)} sensors"
            )
            
        except Exception as e:
            _LOGGER.error(
                f"TRV [{self._room_name}]: Failed to create sensors: {e}"
            )
    
    async def _update_sensors(self):
        """Aktualizuje hodnoty senzorů."""
        try:
            room_slug = self._room_name.lower().replace(" ", "_")
            
            # Aktualizovat všechny senzory
            self._hass.states.async_set(
                f"sensor.trv_{room_slug}_gain",
                self._gain,
                {"friendly_name": f"TRV {self._room_name} Gain", "icon": "mdi:tune"}
            )
            
            self._hass.states.async_set(
                f"sensor.trv_{room_slug}_offset",
                self._offset,
                {
                    "friendly_name": f"TRV {self._room_name} Offset",
                    "unit_of_measurement": "°C",
                    "icon": "mdi:thermometer-lines"
                }
            )
            
            self._hass.states.async_set(
                f"sensor.trv_{room_slug}_oscillation",
                round(self.calculate_oscillation(), 2),
                {
                    "friendly_name": f"TRV {self._room_name} Oscillation",
                    "unit_of_measurement": "°C",
                    "icon": "mdi:wave"
                }
            )
            
            self._hass.states.async_set(
                f"sensor.trv_{room_slug}_last_overshoot",
                round(self._last_overshoot, 2) if self._last_overshoot is not None else 0.0,
                {
                    "friendly_name": f"TRV {self._room_name} Last Overshoot",
                    "unit_of_measurement": "°C",
                    "icon": "mdi:arrow-up-down"
                }
            )
            
            self._hass.states.async_set(
                f"sensor.trv_{room_slug}_learning_cycles",
                len(self._performance_history),
                {
                    "friendly_name": f"TRV {self._room_name} Learning Cycles",
                    "unit_of_measurement": "cycles",
                    "icon": "mdi:counter"
                }
            )
            
            self._hass.states.async_set(
                f"sensor.trv_{room_slug}_state",
                self._state,
                {
                    "friendly_name": f"TRV {self._room_name} State",
                    "icon": "mdi:state-machine"
                }
            )
            
            self._hass.states.async_set(
                f"sensor.trv_{room_slug}_last_trv_target",
                round(self._last_trv_target, 1) if self._last_trv_target is not None else 0.0,
                {
                    "friendly_name": f"TRV {self._room_name} Last TRV Target",
                    "unit_of_measurement": "°C",
                    "icon": "mdi:target"
                }
            )
            
            self._hass.states.async_set(
                f"sensor.trv_{room_slug}_commands_total",
                self._commands_total,
                {
                    "friendly_name": f"TRV {self._room_name} Commands Total",
                    "unit_of_measurement": "commands",
                    "icon": "mdi:counter"
                }
            )
            
        except Exception as e:
            _LOGGER.error(
                f"TRV [{self._room_name}]: Failed to update sensors: {e}"
            )

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
