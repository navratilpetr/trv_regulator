# TRV Regulator Documentation

Dokumentace pro vývojáře a pokročilé uživatele TRV Regulator.

## Pro uživatele

- [README.md](../README.md) - Hlavní dokumentace s instalací a použitím
- [CHANGELOG.md](../CHANGELOG.md) - Historie změn

## Pro vývojáře

- [DEVELOPMENT.md](DEVELOPMENT.md) - Vývojový guide, struktura projektu, debugging
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Jak přispívat do projektu
- [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) - Kodex chování

## Bezpečnost

- [SECURITY.md](../SECURITY.md) - Bezpečnostní politika a hlášení zranitelností

## Architektura

### Hlavní komponenty

```
┌─────────────────────────────────────────────────────┐
│              Home Assistant Core                    │
└─────────────────┬───────────────────────────────────┘
                  │
    ┌─────────────┴───────────────┐
    │   TRV Regulator Integration │
    └─────────────┬───────────────┘
                  │
    ┌─────────────┴───────────────┐
    │                             │
┌───▼────────┐          ┌────────▼─────┐
│Config Flow │          │ Coordinator  │
│            │          │              │
│ • UI setup │          │ • Periodický │
│ • Options  │          │   update     │
│            │          │ • Event      │
└────────────┘          │   handling   │
                        └────────┬─────┘
                                 │
                        ┌────────▼──────────┐
                        │  RoomController   │
                        │                   │
                        │ • State machine   │
                        │ • Learning algo   │
                        │ • TRV control     │
                        │ • Persistence     │
                        └────────┬──────────┘
                                 │
                        ┌────────▼──────────┐
                        │   Sensor Platform │
                        │                   │
                        │ • State sensor    │
                        │ • Learning sensor │
                        │ • Stats sensor    │
                        │ • Diagnostic      │
                        └───────────────────┘
```

### Datový tok

1. **User Input** → Config Flow → ConfigEntry
2. **Sensor Change** → Coordinator → RoomController → State Update
3. **Periodic Update** (30s) → Coordinator → RoomController → Decision
4. **State Change** → RoomController → TRV Commands → Climate entities
5. **Cycle Complete** → RoomController → Storage → Persistence

## Stavový automat

```
IDLE: Teplota OK, TRV vypnuto
  ↓ (temp ≤ target - hysteresis)
HEATING: Topení aktivní
  ↓ (time expired OR temp reached in learning)
COOLDOWN: Měření překmitu (20 min)
  ↓ (cooldown complete)
IDLE

// Speciální stavy
VENT: Okno otevřeno > delay → TRV vypnuto
ERROR: Senzor/TRV offline → TRV vypnuto
```

## Učící algoritmus

### Fáze 1: Learning (prvních N cyklů)

```python
while valid_cycles < learning_cycles_required:
    1. Zapni TRV (35°C)
    2. Čekej na dosažení target
    3. Vypni TRV (5°C)
    4. Měř překmit po dobu cooldown_duration
    5. Validuj cyklus (nebylo přerušení?)
    6. Ulož do historie
```

### Fáze 2: Learned (kontinuální učení)

```python
# Výpočet parametrů z klouzavého průměru
avg_heating_duration = mean(history[-N:].heating_duration)
avg_overshoot = mean(history[-N:].overshoot)

# Prediktivní vypnutí
overshoot_error = avg_overshoot - desired_overshoot
time_offset = overshoot_error * 300  # 300s per 1°C

# Aplikace
planned_duration = avg_heating_duration - time_offset
```

### Klíčové konstanty

- `SECONDS_PER_DEGREE_OVERSHOOT = 300` - Odhad: 300s topení ≈ 1°C překmit
- `DEFAULT_LEARNING_CYCLES = 10` - Počet cyklů pro učení
- `DEFAULT_DESIRED_OVERSHOOT = 0.1` - Cílový překmit v °C
- `HISTORY_SIZE = 100` - Maximální velikost historie

## Persistence

### Storage file
`.storage/trv_regulator_learned_params.json`

### Struktura
```json
{
  "room_name": {
    "avg_heating_duration": 1500,
    "time_offset": 180,
    "is_learning": false,
    "valid_cycles_count": 15,
    "avg_overshoot": 0.15,
    "last_learned": "2026-01-15T20:00:00",
    "history": [
      {
        "timestamp": 1736709600,
        "heating_duration": 1480,
        "overshoot": 0.12,
        "target": 22.0,
        "start_temp": 20.5,
        "stop_temp": 22.0,
        "max_temp": 22.12,
        "valid": true,
        "post_vent": false
      }
    ],
    "monthly_stats": {
      "2026-01": {
        "avg_heating_duration": 1490,
        "avg_overshoot": 0.14,
        "total_cycles": 42,
        "valid_cycles": 38
      }
    }
  }
}
```

## API Reference

### Services

#### `trv_regulator.reset_learned_params`
Resetuje naučené parametry pro místnost.

**Parameters:**
- `entity_id` (optional): Climate entita
- `room` (optional): Název místnosti

**Example:**
```yaml
service: trv_regulator.reset_learned_params
data:
  entity_id: climate.trv_regulator_loznice
```

## Testing

- **Unit tests**: `tests/` - Základní funkčnost
- **Integration tests**: TODO - Testování s mock HA
- **Manual testing**: Instrukce v DEVELOPMENT.md

## Roadmap

Potenciální budoucí vylepšení:
- [ ] Podpora více profilů (eco, comfort, boost)
- [ ] Integrace s weather forecast pro predikci
- [ ] Machine learning pro lepší predikci
- [ ] Grafické UI pro vizualizaci učení
- [ ] Exporty dat (CSV, Excel)
- [ ] REST API pro externí integrace

## Často kladené otázky

**Q: Proč ON/OFF a ne proporcionální řízení?**
A: ON/OFF je jednodušší, spolehlivější a funguje se všemi TRV hlavicemi. Proporcionální řízení vyžaduje přesnou kalibraci a závisí na typu radiátoru.

**Q: Jak dlouho trvá učení?**
A: Výchozích 10 validních cyklů. V praxi 2-4 dny v závislosti na teplotním režimu.

**Q: Můžu změnit rychlost učení?**
A: Ano, změň `learning_cycles_required` v Options (5-30 cyklů).

**Q: Co když se změní podmínky?**
A: Systém se adaptuje pomocí klouzavého průměru. Nebo použij `reset_learned_params` service.

## Reference

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [PID Control Theory](https://en.wikipedia.org/wiki/PID_controller)
- [Kalman Filter](https://en.wikipedia.org/wiki/Kalman_filter) - Inspirace pro predikci
