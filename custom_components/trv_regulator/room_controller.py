"""Stavový automat pro řízení TRV v místnosti - ON/OFF režim s adaptivním učením."""
import asyncio
import json
import logging
import time
import os
from collections import deque
from typing import Any, Optional
from datetime import datetime

from homeassistant.util.json import load_json

from .const import (
    STATE_IDLE,
    STATE_HEATING,
    STATE_COOLDOWN,
    STATE_VENT,
    STATE_ERROR,
    TRV_ON,
    TRV_OFF,
    DEFAULT_LEARNING_CYCLES,
    DEFAULT_DESIRED_OVERSHOOT,
    DEFAULT_MIN_HEATING_DURATION,
    DEFAULT_MAX_HEATING_DURATION,
    DEFAULT_MAX_VALID_OVERSHOOT,
    DEFAULT_COOLDOWN_DURATION,
    HISTORY_SIZE,
    STORAGE_DIR,
    STORAGE_FILE,
    SENSOR_OFFLINE_TIMEOUT,
    TRV_OFFLINE_TIMEOUT,
    TARGET_DEBOUNCE_DELAY,
    TRV_COMMAND_VERIFY_DELAY,
    TRV_TEMP_TOLERANCE,
    FAILURE_REASON_TEMP_MISMATCH,
    FAILURE_REASON_MODE_MISMATCH,
    FAILURE_REASON_OFFLINE,
    FAILURE_REASON_NO_RESPONSE,
    ERROR_LOG_RATE_LIMIT,
)
from .reliability_tracker import ReliabilityTracker

_LOGGER = logging.getLogger(__name__)

# Learning algorithm constants
SECONDS_PER_DEGREE_OVERSHOOT = 300  # Estimate: 300s heating ≈ 1°C overshoot
SIGNIFICANT_DURATION_CHANGE = 10  # seconds - log when avg_duration changes by this much
SIGNIFICANT_OFFSET_CHANGE = 5  # seconds - log when time_offset changes by this much


class RoomController:
    """Stavový automat pro jednu místnost s ON/OFF řízením."""

    def __init__(
        self,
        hass,
        room_name: str,
        temperature_entity: str,
        target_entity: str,
        trv_entities: list[dict],
        window_entities: list[str],
        hysteresis: float,
        window_open_delay: int,
        learning_cycles_required: int = DEFAULT_LEARNING_CYCLES,
        desired_overshoot: float = DEFAULT_DESIRED_OVERSHOOT,
        min_heating_duration: int = DEFAULT_MIN_HEATING_DURATION,
        max_heating_duration: int = DEFAULT_MAX_HEATING_DURATION,
        max_valid_overshoot: float = DEFAULT_MAX_VALID_OVERSHOOT,
        cooldown_duration: int = DEFAULT_COOLDOWN_DURATION,
        recovery_threshold: float = 1.0,
    ):
        """Inicializace controlleru."""
        self._hass = hass
        self._room_name = room_name
        self._temperature_entity = temperature_entity
        self._target_entity = target_entity
        self._trv_entities = trv_entities
        self._window_entities = window_entities
        self._hysteresis = hysteresis
        self._window_open_delay = window_open_delay
        self._learning_cycles_required = learning_cycles_required
        self._desired_overshoot = desired_overshoot
        self._min_heating_duration = min_heating_duration
        self._max_heating_duration = max_heating_duration
        self._max_valid_overshoot = max_valid_overshoot
        self._cooldown_duration = cooldown_duration
        self._recovery_threshold = recovery_threshold

        # Stavový automat
        self._state = STATE_IDLE
        self._window_opened_at = None
        
        # Učení a adaptace
        self._is_learning = True
        self._valid_cycles_count = 0
        self._avg_heating_duration = None
        self._time_offset = 0
        self._avg_overshoot = None
        self._last_learned = None
        
        # POST-VENT režim
        self._post_vent_mode = False
        
        # RECOVERY režim
        self._recovery_mode = False
        
        # Aktuální cyklus
        self._current_cycle = {}
        self._heating_start_time = None
        self._heating_start_temp = None
        self._heating_target_temp = None
        self._cooldown_start_time = None
        self._cooldown_max_temp = None
        
        # Historie cyklů
        self._history = []
        
        # Monthly stats
        self._monthly_stats = {}
        
        # Performance history pro kontinuální učení (klouzavý průměr)
        self._performance_history = deque(maxlen=self._learning_cycles_required)
        
        # Error handling
        self._sensor_unavailable_since = None
        self._trv_unavailable_since = {}
        
        # Target debounce
        self._target_debounce_timer = None
        self._last_target_value = None
        
        # Refresh callback (set by coordinator to avoid circular import)
        self._refresh_callback = None
        
        # Reliability tracking
        self._reliability_tracker = ReliabilityTracker(room_name)
        
        # Rate limiting pro ERROR logy
        self._last_no_response_error_log = {}

        _LOGGER.info(
            f"TRV [{self._room_name}] initialized (ON/OFF mode): "
            f"hysteresis={self._hysteresis}°C, "
            f"window_open_delay={self._window_open_delay}s, "
            f"learning_cycles_required={self._learning_cycles_required}, "
            f"recovery_threshold={self._recovery_threshold}°C"
        )

    @property
    def state(self) -> str:
        """Aktuální stav."""
        return self._state

    @property
    def is_learning(self) -> bool:
        """Zda je v učícím režimu."""
        return self._is_learning

    @property
    def valid_cycles_count(self) -> int:
        """Počet validních naučených cyklů."""
        return self._valid_cycles_count

    @property
    def avg_heating_duration(self) -> Optional[float]:
        """Průměrná doba topení."""
        return self._avg_heating_duration

    @property
    def time_offset(self) -> float:
        """Časový offset pro prediktivní vypnutí."""
        return self._time_offset

    @property
    def avg_overshoot(self) -> Optional[float]:
        """Průměrný překmit."""
        return self._avg_overshoot

    @property
    def last_cycle(self) -> dict:
        """Poslední cyklus."""
        if self._history:
            return self._history[-1]
        return {}

    @property
    def history(self) -> list:
        """Historie cyklů."""
        return self._history

    @property
    def heating_elapsed_seconds(self) -> Optional[float]:
        """Uběhlá doba topení v sekundách."""
        if self._heating_start_time:
            return time.time() - self._heating_start_time
        return None

    @property
    def heating_remaining_seconds(self) -> Optional[float]:
        """Zbývající doba topení v sekundách (pouze v LEARNED režimu)."""
        if not self._is_learning and self._heating_start_time and self._avg_heating_duration:
            planned_duration = self._avg_heating_duration - self._time_offset
            elapsed = time.time() - self._heating_start_time
            return max(0, planned_duration - elapsed)
        return None

    def set_refresh_callback(self, callback):
        """Set the callback for requesting refresh (avoids circular import)."""
        self._refresh_callback = callback

    def reset_cycle_state(self):
        """Reset any in-progress heating cycle (used after restart for safety)."""
        self._heating_start_time = None
        self._cooldown_start_time = None
        self._current_cycle = {}

    def get_temperature(self) -> Optional[float]:
        """Načíst aktuální teplotu (public method)."""
        return self._get_temperature()

    def get_target(self) -> Optional[float]:
        """Načíst cílovou teplotu (public method)."""
        return self._get_target()

    async def _load_learned_params(self):
        """Načíst naučené parametry z úložiště."""
        storage_path = os.path.join(
            self._hass.config.path(STORAGE_DIR),
            STORAGE_FILE
        )
        
        if not os.path.exists(storage_path):
            _LOGGER.info(f"TRV [{self._room_name}]: No learned parameters found, starting fresh")
            return
        
        try:
            # ✅ Async file I/O místo synchronního open():
            data = await self._hass.async_add_executor_job(
                load_json, storage_path
            )
            
            room_data = data.get(self._room_name, {})
            if room_data:
                self._avg_heating_duration = room_data.get("avg_heating_duration")
                self._time_offset = room_data.get("time_offset", 0)
                self._is_learning = room_data.get("is_learning", True)
                self._valid_cycles_count = room_data.get("valid_cycles_count", 0)
                self._last_learned = room_data.get("last_learned")
                self._avg_overshoot = room_data.get("avg_overshoot")
                self._history = room_data.get("history", [])[-HISTORY_SIZE:]
                self._monthly_stats = room_data.get("monthly_stats", {})
                
                # Načíst performance_history
                performance_data = room_data.get("performance_history", [])
                if len(performance_data) > self._learning_cycles_required:
                    _LOGGER.warning(
                        f"TRV [{self._room_name}]: Performance history truncated from "
                        f"{len(performance_data)} to {self._learning_cycles_required} cycles "
                        "(learning_cycles_required changed)"
                    )
                self._performance_history = deque(
                    performance_data,
                    maxlen=self._learning_cycles_required
                )
                
                # Load reliability metrics
                if "reliability_metrics" in room_data:
                    self._reliability_tracker = ReliabilityTracker.from_dict(
                        self._room_name,
                        room_data["reliability_metrics"]
                    )
                    _LOGGER.info(
                        f"TRV [{self._room_name}]: Loaded reliability metrics: "
                        f"commands_sent={self._reliability_tracker._commands_sent_total}, "
                        f"commands_failed={self._reliability_tracker._commands_failed_total}"
                    )
                
                _LOGGER.info(
                    f"TRV [{self._room_name}]: Loaded learned params: "
                    f"avg_duration={self._avg_heating_duration}s, "
                    f"time_offset={self._time_offset}s, "
                    f"is_learning={self._is_learning}, "
                    f"valid_cycles={self._valid_cycles_count}"
                )
        except Exception as e:
            _LOGGER.error(f"TRV [{self._room_name}]: Failed to load learned params: {e}")

    def _aggregate_monthly_stats(self):
        """Agregovat statistiky pro aktuální měsíc."""
        if not self._history:
            return
        
        # Aktuální měsíc
        now = datetime.now()
        current_month = now.strftime("%Y-%m")
        
        # Filtrovat cykly z aktuálního měsíce
        month_cycles = []
        for cycle in self._history:
            cycle_time = datetime.fromtimestamp(cycle["timestamp"])
            if cycle_time.strftime("%Y-%m") == current_month:
                month_cycles.append(cycle)
        
        if not month_cycles:
            return
        
        # Validní cykly
        valid = [c for c in month_cycles if c.get("valid", False)]
        
        if not valid:
            return
        
        # Agregovat
        durations = [c.get("heating_duration", 0) for c in valid]
        overshoots = [c.get("overshoot", 0) for c in valid]
        
        first = datetime.fromtimestamp(month_cycles[0]["timestamp"])
        last = datetime.fromtimestamp(month_cycles[-1]["timestamp"])
        days = (last - first).days + 1
        
        self._monthly_stats[current_month] = {
            "avg_heating_duration": int(sum(durations) / len(durations)),
            "avg_overshoot": round(sum(overshoots) / len(overshoots), 2),
            "total_cycles": len(month_cycles),
            "valid_cycles": len(valid),
            "avg_cycles_per_day": round(len(month_cycles) / days, 1) if days > 0 else 0,
            "first_cycle": first.isoformat(),
            "last_cycle": last.isoformat(),
            "min_heating_duration": int(min(durations)),
            "max_heating_duration": int(max(durations)),
        }
        
        # Cleanup - ponechat jen posledních 24 měsíců
        if len(self._monthly_stats) > 24:
            sorted_months = sorted(self._monthly_stats.keys())
            for old_month in sorted_months[:-24]:
                del self._monthly_stats[old_month]

    async def _save_learned_params(self):
        """Uložit naučené parametry do úložiště."""
        # Agregovat měsíční statistiky
        self._aggregate_monthly_stats()
        
        storage_path = os.path.join(
            self._hass.config.path(STORAGE_DIR),
            STORAGE_FILE
        )
        
        # Načíst existující data
        data = {}
        if os.path.exists(storage_path):
            try:
                # ✅ Async file I/O:
                data = await self._hass.async_add_executor_job(
                    load_json, storage_path
                )
            except Exception as e:
                _LOGGER.warning(f"TRV [{self._room_name}]: Failed to read existing storage: {e}")
        
        # Aktualizovat data pro tuto místnost
        data[self._room_name] = {
            "avg_heating_duration": self._avg_heating_duration,
            "time_offset": self._time_offset,
            "is_learning": self._is_learning,
            "valid_cycles_count": self._valid_cycles_count,
            "last_learned": self._last_learned,
            "avg_overshoot": self._avg_overshoot,
            "history": self._history[-HISTORY_SIZE:],
            "performance_history": list(self._performance_history),
            "monthly_stats": self._monthly_stats,
            "reliability_metrics": self._reliability_tracker.to_dict(),
        }
        
        # Zajistit existenci adresáře
        os.makedirs(os.path.dirname(storage_path), exist_ok=True)
        
        # ✅ Async file I/O - zápis pomocí standardního json.dump:
        def _write_json(path, json_data):
            """Zapsat JSON do souboru."""
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2)
        
        try:
            await self._hass.async_add_executor_job(_write_json, storage_path, data)
            _LOGGER.debug(f"TRV [{self._room_name}]: Saved learned params")
        except Exception as e:
            _LOGGER.error(f"TRV [{self._room_name}]: Failed to save learned params: {e}")

    async def async_update(self):
        """Hlavní update loop."""
        # 1. Kontrola dostupnosti senzoru
        if not await self._check_sensor_availability():
            return
        
        # 2. Kontrola dostupnosti TRV
        if not await self._check_trv_availability():
            return
        
        # 3. Watchdog - kontrola stavu TRV
        await self._verify_trv_state()
        
        # 4. Načíst aktuální hodnoty
        temp = self._get_temperature()
        target = self._get_target()
        
        if temp is None or target is None:
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Waiting for data "
                f"(temp={temp}, target={target})"
            )
            return
        
        # 5. Debounce target změny
        if self._last_target_value != target:
            await self._handle_target_change(target)
            return
        
        # 6. Zkontrolovat okna
        window_open = self._any_window_open()
        
        # 7. Vyhodnotit stavový automat
        new_state = await self._evaluate_state(temp, target, window_open)
        
        # 8. Přejít do nového stavu pokud se změnil
        if new_state != self._state:
            await self._transition_to(new_state, temp, target)
        else:
            # Pokračovat v aktuálním stavu
            await self._continue_in_state(temp, target)

    async def _check_sensor_availability(self) -> bool:
        """Zkontrolovat dostupnost teplotního senzoru."""
        sensor_state = self._hass.states.get(self._temperature_entity)
        
        if sensor_state is None or sensor_state.state in ("unavailable", "unknown"):
            if self._sensor_unavailable_since is None:
                self._sensor_unavailable_since = time.time()
                _LOGGER.warning(
                    f"TRV [{self._room_name}]: Temperature sensor unavailable, waiting..."
                )
            
            elapsed = time.time() - self._sensor_unavailable_since
            if elapsed > SENSOR_OFFLINE_TIMEOUT:
                if self._state != STATE_ERROR:
                    _LOGGER.error(
                        f"TRV [{self._room_name}]: Sensor offline > {SENSOR_OFFLINE_TIMEOUT}s! "
                        "Switching to ERROR state."
                    )
                    await self._transition_to(STATE_ERROR, None, None)
                return False
            
            return False
        
        # Senzor je dostupný, resetovat čítač
        self._sensor_unavailable_since = None
        return True

    async def _check_trv_availability(self) -> bool:
        """Zkontrolovat dostupnost TRV hlavic."""
        for trv_config in self._trv_entities:
            if not trv_config.get("enabled", True):
                continue
            
            entity_id = trv_config["entity"]
            trv_state = self._hass.states.get(entity_id)
            
            if trv_state is None or trv_state.state in ("unavailable", "unknown"):
                if entity_id not in self._trv_unavailable_since:
                    self._trv_unavailable_since[entity_id] = time.time()
                    _LOGGER.warning(
                        f"TRV [{self._room_name}]: TRV {entity_id} unavailable, waiting..."
                    )
                
                elapsed = time.time() - self._trv_unavailable_since[entity_id]
                if elapsed > TRV_OFFLINE_TIMEOUT:
                    if self._state != STATE_ERROR:
                        _LOGGER.error(
                            f"TRV [{self._room_name}]: TRV {entity_id} offline > {TRV_OFFLINE_TIMEOUT}s! "
                            "Switching to ERROR state."
                        )
                        await self._transition_to(STATE_ERROR, None, None)
                    return False
            else:
                # TRV je dostupná, resetovat čítač
                if entity_id in self._trv_unavailable_since:
                    del self._trv_unavailable_since[entity_id]
        
        return True

    async def _handle_target_change(self, new_target):
        """Zpracovat změnu cílové teploty s debounce."""
        self._last_target_value = new_target
        
        # Zrušit existující timer
        if self._target_debounce_timer:
            self._target_debounce_timer.cancel()
        
        # Spustit nový timer
        self._target_debounce_timer = self._hass.loop.call_later(
            TARGET_DEBOUNCE_DELAY,
            lambda: asyncio.create_task(self._target_debounce_expired())
        )
        
        _LOGGER.debug(
            f"TRV [{self._room_name}]: Target changed to {new_target}°C, "
            f"debouncing for {TARGET_DEBOUNCE_DELAY}s"
        )

    async def _target_debounce_expired(self):
        """Debounce timer vypršel, aplikovat změnu."""
        _LOGGER.info(
            f"TRV [{self._room_name}]: Target debounce expired, applying new target"
        )
        
        # Pokud jsme v COOLDOWN, invalidovat aktuální cyklus
        if self._state == STATE_COOLDOWN:
            _LOGGER.info(
                f"TRV [{self._room_name}]: Target changed during COOLDOWN, "
                "invalidating current cycle"
            )
            self._current_cycle["valid"] = False
            self._current_cycle["invalidation_reason"] = "target_changed_during_cooldown"
        
        # Reset POST-VENT flag pokud je změna targetu během HEATING nebo COOLDOWN
        if self._post_vent_mode and self._state in (STATE_HEATING, STATE_COOLDOWN):
            self._post_vent_mode = False
            _LOGGER.debug(
                f"TRV [{self._room_name}]: POST-VENT mode cancelled due to target change"
            )
        
        # Reset RECOVERY flag pokud je změna targetu během HEATING nebo COOLDOWN
        if self._recovery_mode and self._state in (STATE_HEATING, STATE_COOLDOWN):
            self._recovery_mode = False
            _LOGGER.debug(
                f"TRV [{self._room_name}]: RECOVERY mode cancelled due to target change"
            )
        
        # Vynutit refresh pomocí callback
        if self._refresh_callback:
            await self._refresh_callback()
        else:
            _LOGGER.warning(
                f"TRV [{self._room_name}]: Refresh callback not set, cannot request refresh"
            )

    async def _evaluate_state(self, temp: float, target: float, window_open: bool) -> str:
        """Vyhodnotit který stav by měl být aktivní."""
        # ERROR se drží dokud se entity nevrátí
        if self._state == STATE_ERROR:
            return STATE_ERROR
        
        # VENT má přednost
        if window_open:
            if self._window_opened_at is None:
                self._window_opened_at = time.time()
                _LOGGER.info(f"TRV [{self._room_name}]: Window opened")
            
            elapsed = time.time() - self._window_opened_at
            if elapsed >= self._window_open_delay:
                _LOGGER.debug(
                    f"TRV [{self._room_name}]: Window open for {elapsed:.0f}s "
                    f"(>= {self._window_open_delay}s) → VENT"
                )
                return STATE_VENT
        else:
            if self._window_opened_at is not None:
                _LOGGER.info(f"TRV [{self._room_name}]: Window closed")
            self._window_opened_at = None
        
        # VENT režim - čekat na zavření okna
        if self._state == STATE_VENT:
            if not window_open:
                # Okno se zavřelo, okamžitě vyhodnotit regulaci
                return self._evaluate_heating(temp, target)
            return STATE_VENT
        
        # COOLDOWN režim - čekat na vypršení nebo pokles teploty
        if self._state == STATE_COOLDOWN:
            if self._cooldown_start_time:
                elapsed = time.time() - self._cooldown_start_time
                
                # Sledovat maximální teplotu během cooldown
                if self._cooldown_max_temp is None or temp > self._cooldown_max_temp:
                    self._cooldown_max_temp = temp
                
                # Ukončit cooldown pokud:
                # 1. Uplynula doba cooldown_duration
                # 2. NEBO teplota začala klesat (peak byl dosažen)
                if elapsed >= self._cooldown_duration:
                    _LOGGER.info(
                        f"TRV [{self._room_name}]: COOLDOWN duration expired "
                        f"({elapsed:.0f}s >= {self._cooldown_duration}s)"
                    )
                    await self._finish_cooldown(temp, target)
                    return self._evaluate_heating(temp, target)
                elif self._cooldown_max_temp and temp < self._cooldown_max_temp - 0.05:
                    _LOGGER.info(
                        f"TRV [{self._room_name}]: Temperature dropping "
                        f"(peak: {self._cooldown_max_temp:.1f}°C, current: {temp:.1f}°C), "
                        "ending COOLDOWN early"
                    )
                    await self._finish_cooldown(temp, target)
                    return self._evaluate_heating(temp, target)
            
            return STATE_COOLDOWN
        
        # HEATING režim - kontrola času nebo dosažení targetu
        if self._state == STATE_HEATING:
            if self._heating_start_time:
                elapsed = time.time() - self._heating_start_time
                
                # Bezpečnostní vypnutí při překročení max_heating_duration
                if elapsed > self._max_heating_duration:
                    _LOGGER.error(
                        f"TRV [{self._room_name}]: Heating too long ({elapsed/60:.1f} min)! "
                        f"Forcing stop (limit: {self._max_heating_duration/60:.1f} min)."
                    )
                    return STATE_COOLDOWN
                
                # Rozhodnout podle fáze učení
                if self._post_vent_mode or self._is_learning:
                    # POST-VENT nebo LEARNING: topíme dokud nedosáhneme targetu
                    if temp >= target:
                        if self._post_vent_mode:
                            _LOGGER.info(
                                f"TRV [{self._room_name}]: POST-VENT target reached "
                                f"after {elapsed:.0f}s, switching to COOLDOWN"
                            )
                            self._post_vent_mode = False  # Vypnout flag
                        else:
                            # Existující log pro LEARNING režim
                            _LOGGER.info(
                                f"TRV [{self._room_name}]: Target reached in LEARNING mode "
                                f"(temp={temp:.1f}°C >= target={target:.1f}°C) after {elapsed:.0f}s"
                            )
                        return STATE_COOLDOWN
                elif self._recovery_mode:
                    # RECOVERY mode - topíme až do dosažení targetu
                    if temp >= target:
                        _LOGGER.info(
                            f"TRV [{self._room_name}]: RECOVERY mode - target reached "
                            f"({temp:.1f}°C >= {target:.1f}°C) after {elapsed:.0f}s, stopping heating"
                        )
                        self._recovery_mode = False  # Vypnout flag
                        return STATE_COOLDOWN
                else:
                    # LEARNED: vypnout podle času NEBO při dosažení targetu
                    # Bezpečnostní kontrola: pokud nemáme naučené parametry, fallback na čekání na target
                    if self._avg_heating_duration is not None:
                        planned_duration = self._avg_heating_duration - self._time_offset
                        
                        if elapsed >= planned_duration:
                            _LOGGER.info(
                                f"TRV [{self._room_name}]: Predictive shutdown "
                                f"(elapsed={elapsed:.0f}s >= planned={planned_duration:.0f}s)"
                            )
                            return STATE_COOLDOWN
                    
                    # Bezpečnostní vypnutí když dosáhne targetu dříve
                    if temp >= target:
                        _LOGGER.info(
                            f"TRV [{self._room_name}]: Target reached early in LEARNED mode "
                            f"(temp={temp:.1f}°C >= target={target:.1f}°C) "
                            f"after {elapsed:.0f}s"
                        )
                        return STATE_COOLDOWN
            
            return STATE_HEATING
        
        # IDLE nebo jiný stav - vyhodnotit regulaci
        return self._evaluate_heating(temp, target)

    def _evaluate_heating(self, temp: float, target: float) -> str:
        """Vyhodnotit zda zapnout/vypnout topení s asymetrickou hysterezí."""
        lower_threshold = target - self._hysteresis
        
        if self._state == STATE_HEATING:
            # Pokud topíme: vypnout HNED při dosažení cílové teploty
            if temp >= target:
                _LOGGER.debug(
                    f"TRV [{self._room_name}]: Temp {temp:.1f}°C "
                    f">= target {target:.1f}°C → IDLE"
                )
                return STATE_IDLE
            else:
                return STATE_HEATING
        else:
            # Pokud netopíme: zapnout až při poklesu pod lower_threshold
            if temp <= lower_threshold:
                _LOGGER.debug(
                    f"TRV [{self._room_name}]: Temp {temp:.1f}°C "
                    f"<= {lower_threshold:.1f}°C → HEATING"
                )
                return STATE_HEATING
            else:
                return STATE_IDLE

    async def _transition_to(self, new_state: str, temp: Optional[float], target: Optional[float]):
        """Provést přechod do nového stavu."""
        old_state = self._state
        self._state = new_state
        
        _LOGGER.info(
            f"TRV [{self._room_name}]: {old_state.upper()} → {new_state.upper()}"
        )
        
        # Akce podle nového stavu
        if new_state == STATE_HEATING:
            # Detekovat velký teplotní rozdíl → RECOVERY mode
            # Používáme (target - temp) aby RECOVERY aktivoval jen při poklesu (temp < target)
            temp_delta = target - temp
            if temp_delta > self._recovery_threshold:
                self._recovery_mode = True
                _LOGGER.info(
                    f"TRV [{self._room_name}]: Large temperature delta detected "
                    f"({temp_delta:.1f}°C), entering RECOVERY mode"
                )
            else:
                self._recovery_mode = False
            
            # Pokud přecházíme z VENT, zapnout POST-VENT režim
            if old_state == STATE_VENT:
                self._post_vent_mode = True
                _LOGGER.info(
                    f"TRV [{self._room_name}]: Starting POST-VENT heating "
                    "(will heat to target regardless of learned time)"
                )
            
            await self._start_heating(temp, target)
        
        elif new_state == STATE_COOLDOWN:
            await self._start_cooldown(temp, target, old_state)
        
        elif new_state == STATE_IDLE:
            await self._set_all_trv(TRV_OFF)
        
        elif new_state == STATE_VENT:
            # Pokud topíme, invalidovat cyklus
            if old_state == STATE_HEATING:
                _LOGGER.info(
                    f"TRV [{self._room_name}]: Window opened during HEATING, "
                    "invalidating cycle"
                )
                self._current_cycle["valid"] = False
                self._current_cycle["invalidation_reason"] = "window_opened_during_heating"
                # Reset POST-VENT flag pokud byl aktivní
                if self._post_vent_mode:
                    self._post_vent_mode = False
                    _LOGGER.debug(
                        f"TRV [{self._room_name}]: POST-VENT mode cancelled due to window opening"
                    )
                # Reset RECOVERY flag pokud byl aktivní
                if self._recovery_mode:
                    self._recovery_mode = False
                    _LOGGER.debug(
                        f"TRV [{self._room_name}]: RECOVERY mode cancelled due to window opening"
                    )
            elif old_state == STATE_COOLDOWN:
                _LOGGER.info(
                    f"TRV [{self._room_name}]: Window opened during COOLDOWN, "
                    "invalidating cycle"
                )
                self._current_cycle["valid"] = False
                self._current_cycle["invalidation_reason"] = "window_opened_during_cooldown"
            
            await self._set_all_trv(TRV_OFF)
        
        elif new_state == STATE_ERROR:
            await self._set_all_trv(TRV_OFF)

    async def _continue_in_state(self, temp: float, target: float):
        """Pokračovat v aktuálním stavu (žádný přechod)."""
        # V HEATING stavu neděláme nic speciálního
        # V COOLDOWN měříme teplotu (už se děje v _evaluate_state)
        pass

    async def _start_heating(self, temp: float, target: float):
        """Začít topení."""
        self._heating_start_time = time.time()
        self._heating_start_temp = temp
        self._heating_target_temp = target
        
        # Inicializovat nový cyklus
        self._current_cycle = {
            "timestamp": int(self._heating_start_time),
            "start_temp": temp,
            "target": target,
            "valid": True,  # Předpokládáme validitu, může být změněno
            "post_vent": self._post_vent_mode,  # Označit POST-VENT cyklus
        }
        
        await self._set_all_trv(TRV_ON)
        
        if self._post_vent_mode:
            _LOGGER.info(
                f"TRV [{self._room_name}]: Started POST-VENT cycle "
                f"(will heat until target is reached)"
            )
        elif self._recovery_mode:
            temp_delta = target - temp
            _LOGGER.info(
                f"TRV [{self._room_name}]: Started RECOVERY cycle "
                f"(delta={temp_delta:.1f}°C, heating until target)"
            )
        elif self._is_learning:
            _LOGGER.info(
                f"TRV [{self._room_name}]: Started LEARNING cycle "
                f"({self._valid_cycles_count}/{self._learning_cycles_required})"
            )
        else:
            planned_duration = self._avg_heating_duration - self._time_offset
            _LOGGER.info(
                f"TRV [{self._room_name}]: Started LEARNED cycle "
                f"(planned_duration={planned_duration:.0f}s)"
            )

    async def _start_cooldown(self, temp: float, target: float, old_state: str):
        """Začít cooldown měření."""
        self._cooldown_start_time = time.time()
        self._cooldown_max_temp = temp
        
        # Uložit dobu topení
        if self._heating_start_time:
            heating_duration = self._cooldown_start_time - self._heating_start_time
            self._current_cycle["heating_duration"] = heating_duration
            self._current_cycle["stop_temp"] = temp
            
            _LOGGER.info(
                f"TRV [{self._room_name}]: Heating stopped after {heating_duration:.0f}s, "
                f"entering COOLDOWN"
            )
        
        await self._set_all_trv(TRV_OFF)

    async def _finish_cooldown(self, temp: float, target: float):
        """Dokončit cooldown a uložit cyklus."""
        if not self._current_cycle:
            return
        
        # Vypočítat překmit
        overshoot = (self._cooldown_max_temp or temp) - target
        self._current_cycle["max_temp"] = self._cooldown_max_temp or temp
        self._current_cycle["overshoot"] = overshoot
        
        # Validovat cyklus
        is_valid = self._is_cycle_valid(self._current_cycle)
        self._current_cycle["valid"] = is_valid
        
        # Uložit do historie
        self._history.append(self._current_cycle)
        if len(self._history) > HISTORY_SIZE:
            self._history = self._history[-HISTORY_SIZE:]
        
        _LOGGER.info(
            f"TRV [{self._room_name}]: Cycle finished - "
            f"duration={self._current_cycle.get('heating_duration', 0):.0f}s, "
            f"overshoot={overshoot:.2f}°C, valid={is_valid}"
        )
        
        # Pokud je validní, aplikovat učení
        if is_valid:
            await self._apply_learning()
        
        # Uložit parametry
        await self._save_learned_params()
        
        # Reset proměnných
        self._heating_start_time = None
        self._cooldown_start_time = None
        self._cooldown_max_temp = None
        self._current_cycle = {}

    def _is_cycle_valid(self, cycle: dict) -> bool:
        """Zkontrolovat zda je cyklus validní pro učení."""
        # Pokud byl manuálně invalidován (okno, změna targetu)
        if not cycle.get("valid", True):
            return False
        
        # POST-VENT cykly nepoužívat pro učení
        if cycle.get("post_vent", False):
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Cycle invalid - POST-VENT recovery cycle "
                "(not used for learning)"
            )
            return False
        
        heating_duration = cycle.get("heating_duration", 0)
        overshoot = cycle.get("overshoot", 0)
        stop_temp = cycle.get("stop_temp", 0)
        target = cycle.get("target", 0)
        
        # Kontroly
        if heating_duration < self._min_heating_duration:
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Cycle invalid - too short "
                f"({heating_duration:.0f}s < {self._min_heating_duration}s)"
            )
            return False
        
        if heating_duration > self._max_heating_duration:
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Cycle invalid - too long "
                f"({heating_duration:.0f}s > {self._max_heating_duration}s)"
            )
            return False
        
        if stop_temp < target - 1.0:
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Cycle invalid - didn't reach near target "
                f"({stop_temp:.1f}°C < {target - 1.0:.1f}°C)"
            )
            return False
        
        if overshoot > self._max_valid_overshoot:
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Cycle invalid - excessive overshoot "
                f"({overshoot:.2f}°C > {self._max_valid_overshoot}°C)"
            )
            return False
        
        return True

    async def _apply_learning(self):
        """Aplikovat učení z validního cyklu s kontinuálním učením."""
        # Přidat aktuální cyklus do performance_history pokud je validní
        if self._current_cycle.get("valid", False):
            # Validate that required keys exist
            if all(key in self._current_cycle for key in ["heating_duration", "overshoot", "timestamp"]):
                self._performance_history.append({
                    "heating_duration": self._current_cycle["heating_duration"],
                    "overshoot": self._current_cycle["overshoot"],
                    "timestamp": self._current_cycle["timestamp"],
                })
            else:
                _LOGGER.warning(
                    f"TRV [{self._room_name}]: Current cycle missing required keys, skipping learning"
                )
        
        # Spočítat validní cykly
        valid_cycles = [c for c in self._history if c.get("valid", False)]
        self._valid_cycles_count = len(valid_cycles)
        
        # Pokud máme alespoň learning_cycles_required cyklů v performance_history
        if len(self._performance_history) >= self._learning_cycles_required:
            # PŘEPOČÍTAT z posledních N cyklů (klouzavý průměr)
            durations = [c["heating_duration"] for c in self._performance_history]
            overshoots = [c["overshoot"] for c in self._performance_history]
            
            new_avg_duration = sum(durations) / len(durations)
            new_avg_overshoot = sum(overshoots) / len(overshoots)
            
            # Vypočítat nový time_offset
            new_time_offset = self._calculate_time_offset(
                new_avg_duration,
                new_avg_overshoot
            )
            
            # Logovat změny pokud jsou významné
            is_first_learning = (self._avg_heating_duration is None)
            
            if is_first_learning:
                # První naučení - systém dokončil počáteční učící fázi
                _LOGGER.info(
                    f"TRV [{self._room_name}]: LEARNING COMPLETE! "
                    f"avg_duration={new_avg_duration:.0f}s, "
                    f"avg_overshoot={new_avg_overshoot:.2f}°C, "
                    f"time_offset={new_time_offset:.0f}s "
                    f"(z posledních {len(self._performance_history)} cyklů)"
                )
                self._is_learning = False
            else:
                # Kontinuální úprava - logovat jen pokud je změna > SIGNIFICANT_*_CHANGE
                duration_change = abs(new_avg_duration - self._avg_heating_duration)
                offset_change = abs(new_time_offset - self._time_offset)
                
                if duration_change > SIGNIFICANT_DURATION_CHANGE or offset_change > SIGNIFICANT_OFFSET_CHANGE:
                    _LOGGER.info(
                        f"TRV [{self._room_name}]: Parameters updated: "
                        f"avg_duration {self._avg_heating_duration:.0f}s → {new_avg_duration:.0f}s, "
                        f"time_offset {self._time_offset:.0f}s → {new_time_offset:.0f}s "
                        f"(klouzavý průměr z {len(self._performance_history)} cyklů)"
                    )
            
            # Aplikovat nové hodnoty
            self._avg_heating_duration = new_avg_duration
            self._avg_overshoot = new_avg_overshoot
            self._time_offset = new_time_offset
            self._last_learned = datetime.now().isoformat()
        elif self._is_learning and self._avg_heating_duration is None:
            # Stále učíme a nemáme ještě dost cyklů - neděláme nic
            _LOGGER.debug(
                f"TRV [{self._room_name}]: Learning in progress "
                f"({len(self._performance_history)}/{self._learning_cycles_required} cycles)"
            )

    def _calculate_time_offset(self, avg_duration: float, avg_overshoot: float) -> float:
        """Vypočítat počáteční time_offset."""
        # Cíl: overshoot blízko desired_overshoot
        overshoot_error = avg_overshoot - self._desired_overshoot
        
        # Konzervativní odhad: SECONDS_PER_DEGREE_OVERSHOOT na 1°C
        time_offset = overshoot_error * SECONDS_PER_DEGREE_OVERSHOOT
        
        # Limit: max 50% z avg_duration
        max_offset = avg_duration * 0.5
        time_offset = max(-max_offset, min(max_offset, time_offset))
        
        return time_offset

    async def _set_all_trv(self, command: dict[str, Any]):
        """Nastavit všechny TRV hlavice s verifikací."""
        mode = command["hvac_mode"]
        temp = command["temperature"]
        
        active_count = sum(1 for trv in self._trv_entities if trv.get("enabled", True))
        
        _LOGGER.info(
            f"TRV [{self._room_name}]: Setting {active_count} TRV(s) to "
            f"{mode.upper()} ({temp}°C)"
        )
        
        # 1️⃣ Zaznamenat last_seen PŘED příkazem
        last_seen_before = {}
        for trv_config in self._trv_entities:
            if not trv_config.get("enabled", True):
                continue
            
            entity_id = trv_config["entity"]
            last_seen_sensor = trv_config.get("last_seen_sensor")
            
            if last_seen_sensor:
                sensor_state = self._hass.states.get(last_seen_sensor)
                if sensor_state and sensor_state.state not in ("unavailable", "unknown"):
                    last_seen_before[entity_id] = sensor_state.state
                else:
                    _LOGGER.warning(
                        f"TRV [{self._room_name}]: {entity_id} last_seen sensor unavailable"
                    )
        
        # 2️⃣ Track command + poslat příkazy
        for trv_config in self._trv_entities:
            if not trv_config.get("enabled", True):
                continue
            
            entity_id = trv_config["entity"]
            
            # Track command sent
            self._reliability_tracker.command_sent(entity_id)
            
            await self._hass.services.async_call(
                "climate",
                "set_hvac_mode",
                {"entity_id": entity_id, "hvac_mode": mode},
                blocking=True,
            )
            
            await self._hass.services.async_call(
                "climate",
                "set_temperature",
                {"entity_id": entity_id, "temperature": temp},
                blocking=True,
            )
        
        # 3️⃣ Počkat a ověřit stav
        await asyncio.sleep(TRV_COMMAND_VERIFY_DELAY)
        
        # 4️⃣ Verifikovat že všechny TRV přijaly příkaz
        for trv_config in self._trv_entities:
            if not trv_config.get("enabled", True):
                continue
            
            entity_id = trv_config["entity"]
            trv_state = self._hass.states.get(entity_id)
            
            if not trv_state or trv_state.state == "unavailable":
                self._reliability_tracker.command_failed(
                    entity_id,
                    expected={"hvac_mode": mode, "temperature": temp},
                    actual={"state": "unavailable"},
                    reason=FAILURE_REASON_OFFLINE
                )
                continue
            
            actual_temp = trv_state.attributes.get("temperature")
            actual_mode = trv_state.state
            
            # Temperature check (existující logika)
            temp_ok = actual_temp is not None and abs(actual_temp - temp) <= TRV_TEMP_TOLERANCE
            
            # 🆕 Last seen check
            if entity_id in last_seen_before:
                last_seen_sensor = trv_config.get("last_seen_sensor")
                sensor_state = self._hass.states.get(last_seen_sensor)
                
                if sensor_state and sensor_state.state not in ("unavailable", "unknown"):
                    last_seen_after = sensor_state.state
                    
                    if last_seen_after == last_seen_before[entity_id]:
                        # ❌ Last_seen se NEZMĚNIL = TRV neodpověděla
                        if self._should_log_no_response_error(entity_id):
                            _LOGGER.error(
                                f"TRV [{self._room_name}]: {entity_id} NOT RESPONDING! "
                                f"Last seen unchanged ({last_seen_after}). Check battery/signal."
                            )
                        
                        self._reliability_tracker.command_failed(
                            entity_id,
                            expected={"hvac_mode": mode, "temperature": temp},
                            actual={"last_seen": last_seen_after},
                            reason=FAILURE_REASON_NO_RESPONSE
                        )
                        continue
                    else:
                        # ✅ Last_seen se změnil = TRV odpověděla
                        _LOGGER.debug(
                            f"TRV [{self._room_name}]: {entity_id} responded "
                            f"(last_seen: {last_seen_before[entity_id]} → {last_seen_after})"
                        )
            
            # Existing temperature/mode verification...
            if not temp_ok:
                # CRITICAL ERROR - temperature mismatch!
                _LOGGER.error(
                    f"TRV [{self._room_name}]: {entity_id} FAILED to apply temperature! "
                    f"Expected: {temp}°C, Got: {actual_temp}°C - Command likely lost due to weak signal"
                )
                self._reliability_tracker.command_failed(
                    entity_id,
                    expected={"hvac_mode": mode, "temperature": temp},
                    actual={"hvac_mode": actual_mode, "temperature": actual_temp},
                    reason=FAILURE_REASON_TEMP_MISMATCH
                )
            elif actual_mode != mode:
                # WARNING - mode mismatch but temperature OK (TRV preference)
                _LOGGER.warning(
                    f"TRV [{self._room_name}]: {entity_id} mode differs (expected: {mode}, got: {actual_mode}) "
                    f"but temperature is correct ({actual_temp}°C) - TRV prefers {actual_mode} mode"
                )
                self._reliability_tracker.mode_mismatch(
                    entity_id,
                    expected_mode=mode,
                    actual_mode=actual_mode,
                    temperature=actual_temp
                )
            else:
                _LOGGER.debug(
                    f"TRV [{self._room_name}]: {entity_id} verified OK ({actual_mode}/{actual_temp}°C)"
                )

    async def _verify_trv_state(self):
        """Pravidelná kontrola, zda TRV odpovídají očekávanému stavu."""
        # Určit očekávaný příkaz podle aktuálního stavu
        if self._state == STATE_HEATING:
            expected_command = TRV_ON
        else:
            # IDLE, COOLDOWN, VENT, ERROR → všechny mají TRV OFF
            expected_command = TRV_OFF
        
        expected_temp = expected_command["temperature"]
        expected_mode = expected_command["hvac_mode"]
        
        for trv_config in self._trv_entities:
            if not trv_config.get("enabled", True):
                continue
            
            entity_id = trv_config["entity"]
            trv_state = self._hass.states.get(entity_id)
            
            if not trv_state or trv_state.state in ("unavailable", "unknown"):
                continue  # TRV offline je řešeno v _check_trv_availability
            
            actual_temp = trv_state.attributes.get("temperature")
            actual_mode = trv_state.state
            
            # Smart watchdog - check only temperature!
            temp_mismatch = actual_temp is not None and abs(actual_temp - expected_temp) > TRV_TEMP_TOLERANCE
            
            if temp_mismatch:
                # REAL mismatch - temperature is wrong!
                _LOGGER.warning(
                    f"TRV [{self._room_name}]: {entity_id} STATE MISMATCH detected! "
                    f"Expected: {expected_temp}°C, Actual: {actual_temp}°C (mode: {actual_mode}) - CORRECTING NOW"
                )
                
                # Track watchdog correction
                self._reliability_tracker.watchdog_correction(
                    entity_id,
                    expected={"hvac_mode": expected_mode, "temperature": expected_temp},
                    found={"hvac_mode": actual_mode, "temperature": actual_temp},
                    reason=FAILURE_REASON_TEMP_MISMATCH
                )
                
                # Okamžitě opravit
                await self._hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {"entity_id": entity_id, "hvac_mode": expected_mode},
                    blocking=True,
                )
                
                await self._hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {"entity_id": entity_id, "temperature": expected_temp},
                    blocking=True,
                )

    def _should_log_no_response_error(self, entity_id: str) -> bool:
        """Rozhodnout jestli logovat NO_RESPONSE ERROR (max 1x/30min)."""
        now = time.time()
        last_log = self._last_no_response_error_log.get(entity_id, 0)
        
        if now - last_log < ERROR_LOG_RATE_LIMIT:
            return False  # Skip
        
        self._last_no_response_error_log[entity_id] = now
        return True  # Log

    def _get_temperature(self) -> Optional[float]:
        """Načíst aktuální teplotu."""
        state = self._hass.states.get(self._temperature_entity)
        if state and state.state not in ("unavailable", "unknown"):
            try:
                return float(state.state)
            except ValueError:
                _LOGGER.error(
                    f"TRV [{self._room_name}]: Invalid temperature value: {state.state}"
                )
        return None

    def _get_target(self) -> Optional[float]:
        """Načíst cílovou teplotu."""
        state = self._hass.states.get(self._target_entity)
        if state and state.state not in ("unavailable", "unknown"):
            try:
                return float(state.state)
            except ValueError:
                _LOGGER.error(
                    f"TRV [{self._room_name}]: Invalid target value: {state.state}"
                )
        return None

    def _any_window_open(self) -> bool:
        """Zkontrolovat zda je nějaké okno otevřeno."""
        for entity_id in self._window_entities:
            state = self._hass.states.get(entity_id)
            if state and state.state == "on":
                return True
        return False

    async def reset_learned_params(self):
        """Manuálně resetovat naučené parametry."""
        _LOGGER.warning(
            f"TRV [{self._room_name}]: Resetting learned parameters - "
            "starting fresh learning"
        )
        
        # Reset parametrů
        self._avg_heating_duration = None
        self._time_offset = 0
        self._avg_overshoot = None
        self._is_learning = True
        self._valid_cycles_count = 0
        self._last_learned = None
        
        # Smazat historii
        self._history.clear()
        self._performance_history.clear()
        
        # Uložit do JSON
        await self._save_learned_params()
        
        _LOGGER.info(
            f"TRV [{self._room_name}]: Reset complete, learning mode activated "
            f"({self._learning_cycles_required} cycles required)"
        )
