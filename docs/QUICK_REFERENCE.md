# Quick Reference

## Příkazy pro vývojáře

```bash
# Setup
make install              # Nainstalovat závislosti
make dev-setup           # Kompletní dev setup

# Testování
make test                # Spustit testy
make test-cov            # Testy s coverage reportem
pytest tests/test_const.py  # Konkrétní test

# Code Quality
make lint                # Linting (ruff)
make lint-fix            # Automatické opravy
make format              # Formátování (black)
make type-check          # Type checking (mypy)
make check               # Všechny checks najednou

# Pre-commit
make pre-commit          # Spustit všechny pre-commit hooks
pre-commit run --all-files  # Stejné jako make pre-commit

# Čištění
make clean               # Vyčistit build artifacts
```

## Konfigurační parametry

| Parametr | Výchozí | Rozsah | Popis |
|----------|---------|---------|-------|
| `hysteresis` | 0.3°C | 0.0-2.0 | Rozsah pro přepínání |
| `window_open_delay` | 120s | 30-600 | Zpoždění větrání |
| `learning_cycles_required` | 10 | 5-30 | Počet cyklů pro učení |
| `desired_overshoot` | 0.1°C | 0.0-0.5 | Cílový překmit |
| `min_heating_duration` | 180s | 60-600 | Min. doba topení |
| `max_heating_duration` | 7200s | 900-10800 | Max. doba topení |
| `max_valid_overshoot` | 3.0°C | 1.0-5.0 | Max. platný překmit |
| `cooldown_duration` | 1200s | 600-1800 | Doba měření překmitu |

## Stavový automat

| Stav | TRV | Trvání | Přechod do |
|------|-----|--------|------------|
| IDLE | OFF (5°C) | ∞ | HEATING, VENT, ERROR |
| HEATING | ON (35°C) | calculated | COOLDOWN |
| COOLDOWN | OFF (5°C) | 20 min | IDLE, HEATING |
| VENT | OFF (5°C) | ∞ | IDLE, HEATING |
| ERROR | OFF (5°C) | ∞ | IDLE |

## Podmínky přechodů

```python
IDLE → HEATING:
    temp ≤ target - hysteresis

HEATING → COOLDOWN:
    (learned) time >= avg_duration - offset
    (learning) temp >= target

COOLDOWN → IDLE:
    time >= cooldown_duration OR temp_decreasing

COOLDOWN → HEATING:
    temp ≤ target - hysteresis

* → VENT:
    window_open > window_open_delay

VENT → IDLE/HEATING:
    window_closed (evaluate immediately)

* → ERROR:
    sensor_offline > 120s OR trv_offline > 300s

ERROR → IDLE:
    all_entities_available
```

## Senzory

| Sensor | Stav | Atributy |
|--------|------|----------|
| `sensor.trv_regulator_{room}_state` | Aktuální stav | temp, target, elapsed, remaining |
| `sensor.trv_regulator_{room}_learning` | learning/learned | cycles, avg_duration, offset, overshoot |
| `sensor.trv_regulator_{room}_last_cycle` | Timestamp | duration, overshoot, temps, valid |
| `sensor.trv_regulator_{room}_history` | Počet cyklů | cycles[] (až 100) |
| `sensor.trv_regulator_{room}_stats` | Statistiky | total/valid cycles, avg/min/max |
| `sensor.trv_regulator_{room}_diagnostics` | Health status | entity states, config |
| `sensor.trv_regulator_summary` | Přehled | all rooms summary |

## Service Calls

### Reset naučených parametrů
```yaml
service: trv_regulator.reset_learned_params
data:
  entity_id: climate.trv_regulator_loznice
  # NEBO
  room: loznice
```

## Logování

### Nastavení debug logu
```yaml
# configuration.yaml
logger:
  default: info
  logs:
    custom_components.trv_regulator: debug
```

### Sledování logů
```bash
# Linux/Mac
tail -f ~/.homeassistant/home-assistant.log | grep "TRV"

# Docker
docker logs -f homeassistant | grep "TRV"
```

### Důležité log zprávy
```
TRV [Room]: IDLE → HEATING
TRV [Room]: Started LEARNING cycle (3/10)
TRV [Room]: Heating stopped after 1450s, entering COOLDOWN
TRV [Room]: Cycle finished - duration=1450s, overshoot=0.25°C, valid=true
TRV [Room]: LEARNING COMPLETE! avg_duration=1440s, time_offset=45s
TRV [Room]: Adjusted time_offset: 45s → 57s
```

## Troubleshooting

### TRV se nespínají
```bash
# Zkontroluj dostupnost
states | grep climate.your_trv

# Zkontroluj podporované funkce
service climate.turn_on entity_id=climate.your_trv
service climate.set_temperature entity_id=climate.your_trv temperature=35
```

### Učení trvá dlouho
```bash
# Zkontroluj validní cykly
states sensor.trv_regulator_room_learning

# Možné důvody:
# - Časté otevírání oken (invaliduje cykly)
# - Změny target teploty (invaliduje cykly)
# - Restartování HA během topení
```

### ERROR stav
```bash
# Zkontroluj dostupnost senzorů
states sensor.your_temperature
states climate.your_trv

# Senzor offline > 2 min → ERROR
# TRV offline > 5 min → ERROR
```

## Vzorce

### Prediktivní vypnutí
```python
avg_heating_duration = mean(last_N_cycles.heating_duration)
avg_overshoot = mean(last_N_cycles.overshoot)
overshoot_error = avg_overshoot - desired_overshoot
time_offset = overshoot_error * 300  # seconds per degree
planned_duration = avg_heating_duration - time_offset
```

### Validace cyklu
```python
valid = (
    not interrupted_by_window and
    not target_changed and
    not ha_restarted and
    min_duration < duration < max_duration and
    overshoot < max_valid_overshoot and
    not post_vent_cycle
)
```

## Git Workflow

```bash
# Vytvoř branch
git checkout -b feature/nova-funkce

# Změny
git add .
git commit -m "feat: přidána nová funkce"

# Push
git push origin feature/nova-funkce

# PR na GitHubu
# Přidej label: breaking/feature/(none for patch)
```

## Version Bumping

- `breaking` label → major version (3.0.0 → 4.0.0)
- `feature` label → minor version (3.0.0 → 3.1.0)
- žádný label → patch version (3.0.0 → 3.0.1)

## Užitečné odkazy

- [Dokumentace](README.md)
- [Development Guide](DEVELOPMENT.md)
- [Contributing](../CONTRIBUTING.md)
- [Security](../SECURITY.md)
- [HA Developer Docs](https://developers.home-assistant.io/)
