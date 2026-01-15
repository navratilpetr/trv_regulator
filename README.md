# TRV Regulator

[![GitHub Release](https://img.shields.io/github/v/release/navratilpetr/trv_regulator)](https://github.com/navratilpetr/trv_regulator/releases)
[![CI](https://github.com/navratilpetr/trv_regulator/actions/workflows/ci.yaml/badge.svg)](https://github.com/navratilpetr/trv_regulator/actions/workflows/ci.yaml)
[![CodeQL](https://github.com/navratilpetr/trv_regulator/actions/workflows/codeql.yaml/badge.svg)](https://github.com/navratilpetr/trv_regulator/actions/workflows/codeql.yaml)
[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Custom integrace pro Home Assistant - **ON/OFF řízení s adaptivním učením** pro vytápění po místnostech pomocí TRV hlavic.

## ✨ Vlastnosti

- **ON/OFF řízení:** TRV buď zapnutá (35°C) nebo vypnutá (5°C) - žádná proporcionální regulace
- **Učící režim:** Prvních 10 cyklů měří dobu potřebnou k ohřátí místnosti
- **Prediktivní vypínání:** Po naučení vypíná podle času (ne teploty) aby minimalizoval překmit
- **Adaptivní úprava:** Průběžně upravuje timing podle skutečného překmitu
- **Validace cyklů:** Ignoruje cykly přerušené okny, změnou targetu, atd.
- **Větrání:** Automatické vypnutí topení při otevření okna (konfigurovatelný debounce)
- **Multi-TRV:** Podpora více termostatických hlavic v jedné místnosti
- **Diagnostické senzory:** Sledování stavu, učení, historie cyklů
- **Config Flow:** Kompletní konfigurace přes UI (bez YAML)
- **Persistence:** Ukládá naučené parametry a historii posledních 100 cyklů

### 🆕 Pokročilé funkce (v3.0.9)

- ✅ **POST-VENT režim** - Automatické inteligentní dotopení po větrání
  - Systém detekuje zavření okna a automaticky přepne do režimu "dotápění"
  - První topný cyklus po větrání ignoruje naučený čas a topí až do dosažení cílové teploty
  - Řeší problém nedotopení po větším poklesu teploty během větrání
  
- 🎛️ **Výběr aktivních TRV hlavic**
  - V místnostech s více TRV hlavicemi lze jednotlivé hlavice vypnout přes UI
  - Nastavení → Integrace → TRV Regulator → Možnosti
  
- 🔧 **Manuální reset parametrů**
  - Service pro reset naučených parametrů: `trv_regulator.reset_learned_params`
  - Užitečné po výměně radiátoru, TRV hlavice nebo změně podmínek

## 📦 Instalace

### Pomocí HACS (doporučeno)

1. Otevři HACS v Home Assistant
2. Klikni na "Integrace"
3. Klikni na tři tečky vpravo nahoře a vyber "Vlastní repozitáře"
4. Přidej URL: `https://github.com/navratilpetr/trv_regulator`
5. Kategorie: `Integration`
6. Klikni "Přidat"
7. Najdi "TRV Regulator" v HACS a klikni "Stáhnout"
8. Restartuj Home Assistant
9. Přidej integraci: Nastavení → Zařízení a služby → Přidat integraci → "TRV Regulator"

### Ruční instalace

1. Zkopíruj složku `custom_components/trv_regulator` do tvé Home Assistant konfigurace:
   ```bash
   cd /config/custom_components
   git clone https://github.com/navratilpetr/trv_regulator.git
   cp -r trv_regulator/custom_components/trv_regulator ./
   ```
2. Restartuj Home Assistant
3. Přidej integraci přes UI: Nastavení → Zařízení a služby → Přidat integraci → "TRV Regulator"

## 🔧 Konfigurace

### Povinné entity:
- **Senzor teploty** - aktuální naměřená teplota v místnosti (Zigbee senzor)
- **Cílová teplota** - požadovaná teplota místnosti (input_number)
- **TRV hlavice** - jeden nebo více termostatů

### Volitelné entity a parametry:
- **Okna** - binary senzory pro detekci větrání
- **Hystereze** - rozsah teplot pro přepínání stavů (0.0-2.0°C, výchozí: 0.3°C)
- **Zpoždění větrání** - čas do aktivace větrání (30-600s, výchozí: 120s)

### Parametry učení:
- **Počet cyklů pro učení** - velikost klouzavého průměru (5-30, výchozí: 10)
  - Menší číslo (5) = rychlejší adaptace na změny
  - Větší číslo (20) = pomalejší adaptace, stabilnější
- **Požadovaný překmit** - cílový překmit v °C (0.0-0.5°C, výchozí: 0.1°C)
- **Min. doba topení** - minimální validní doba topení (60-600s, výchozí: 180s / 3 min)
- **Max. doba topení** - maximální validní doba topení (900-10800s, výchozí: 7200s / 120 min)
- **Max. validní překmit** - maximální přípustný překmit (1.0-5.0°C, výchozí: 3.0°C)
- **Doba cooldown** - jak dlouho měřit překmit (600-1800s, výchozí: 1200s / 20 min)

## 🎯 ON/OFF řízení s adaptivním učením

### Jak to funguje

Integrace používá **dvoustupňové ON/OFF řízení** s časovým prediktivním vypínáním:

#### Fáze 1: LEARNING (prvních X cyklů)

```
1. Zapne TRV na 35°C
2. Topí dokud teplota nedosáhne targetu
3. Měří kolik to trvalo (heating_duration)
4. Vypne TRV na 5°C
5. Měří překmit (max. teplota - target) po dobu 20 min
6. Validuje cyklus (nebyl přerušen oknem, změnou targetu, atd.)
7. Po 10 validních cyklech vypočítá:
   - avg_heating_duration (průměrná doba topení)
   - time_offset (kolik sekund dřív vypnout)
```

#### Fáze 2: LEARNED (kontinuální učení s klouzavým průměrem)

```
1. Zapne TRV na 35°C
2. Vypne když:
   - Uplyne plánovaný čas: avg_heating_duration - time_offset
   - NEBO dosáhne cílové teploty (bezpečnostní pojistka)
3. Měří skutečný překmit
4. Po každém validním cyklu přepočítá parametry z posledních N cyklů:
   - Přidá nový cyklus, odstraní nejstarší
   - Přepočítá avg_heating_duration a time_offset z klouzavého průměru
   - Automatická adaptace na změny počasí
```

### Příklad

**Místnost:** Kuchyň, target 22°C

**Learning fáze (prvních 10 cyklů):**
```
Cyklus 1: Topí 25 min, dosáhne 22°C, překmit 0.3°C ✓ validní
Cyklus 2: Topí 23 min, dosáhne 22°C, překmit 0.2°C ✓ validní
Cyklus 3: Okno otevřeno po 10 min ✗ nevalidní (ignorovat)
...
Cyklus 11: 10 validních cyklů → průměr 24 min, překmit 0.25°C

Výpočet:
avg_heating_duration = 1440s (24 min)
avg_overshoot = 0.25°C
desired_overshoot = 0.1°C
→ time_offset = (0.25 - 0.1) × 300 = 45s
```

**Learned fáze:**
```
Zapne TRV, topí 1440s - 45s = 1395s (23:15 min)
Vypne PŘED dosažením targetu
Měří překmit: 0.12°C ✓ blízko cíli (0.1°C)

Cyklus 12 (po naučení):
Překmit 0.3°C

Klouzavý průměr z posledních 10 cyklů:
- Odstraní cyklus 1, přidá cyklus 12
- Nový avg_overshoot = 0.27°C
- Přepočítá time_offset = (0.27 - 0.1) × 300 = 51s
→ Příště vypne o 51s dřív (postupná adaptace)
```

## 📊 Stavový automat

```
IDLE ←→ HEATING ←→ COOLDOWN
  ↕       ↕           ↕
VENT ←→ (pause)    (pause)
  ↕
ERROR
```

### Stavy:
- **idle** - Teplota OK, TRV vypnutá (5°C)
- **heating** - Aktivně topí, TRV zapnutá (35°C)
- **cooldown** - Po vypnutí, měří překmit (20 min), TRV vypnutá (5°C)
- **vent** - Okno otevřeno > delay, TRV vypnutá (5°C)
- **error** - Senzor/TRV offline, TRV vypnutá (5°C)

### Přechody:
- `IDLE → HEATING`: teplota ≤ target − hystereze
- `HEATING → COOLDOWN`: vypršel čas topení (nebo dosažen target při učení)
- `COOLDOWN → IDLE`: uplynulo 20 min NEBO teplota klesá
- `COOLDOWN → HEATING`: teplota < target − hystereze (nový cyklus)
- `* → VENT`: okno otevřeno > window_open_delay
- `VENT → IDLE/HEATING`: okno se zavře (okamžitě vyhodnotit)
- `* → ERROR`: senzor offline > 2 min NEBO TRV offline > 5 min

## 📊 Diagnostické senzory

Pro každou místnost se automaticky vytvoří tyto senzory:

### 1. `sensor.trv_regulator_{room}_state`
Aktuální stav automatu s atributy:
```yaml
state: "heating"
attributes:
  current_temp: 21.5
  target_temp: 22.0
  heating_start_time: "2026-01-12T18:30:00"
  heating_elapsed_seconds: 450
  heating_remaining_seconds: 1050  # pouze v LEARNED režimu
```

### 2. `sensor.trv_regulator_{room}_learning`
Stav učení s parametry:
```yaml
state: "learned"
attributes:
  valid_cycles: 15
  required_cycles: 10
  avg_heating_duration: 1500  # sekund
  time_offset: 180  # sekund
  avg_overshoot: 0.15  # °C
```

### 3. `sensor.trv_regulator_{room}_last_cycle`
Poslední topný cyklus:
```yaml
state: "2026-01-12T18:00:00"
attributes:
  heating_duration: 1480  # sekund
  overshoot: 0.12  # °C
  start_temp: 20.5
  stop_temp: 22.0
  max_temp: 22.12
  valid: true
```

### 4. `sensor.trv_regulator_{room}_history`
Historie cyklů:
```yaml
state: 100  # počet cyklů
attributes:
  cycles:
    - timestamp: 1736709600
      heating_duration: 1480
      overshoot: 0.12
      valid: true
    # ... až 100 cyklů
```

## ⚙️ Reagování na události

### Teplota pokoje (Zigbee senzor):
- ✅ Reaguje na **každou změnu** (senzor posílá jen při změně)
- ✅ Spustí update okamžitě

### Cílová teplota (input_number):
- ✅ **Debounce 15 sekund** (uživatel posouvá slider)
- ✅ Po 15s bez změny → aplikuje změnu
- ✅ Během debounce zruší předchozí timer

### Stav oken:
- ✅ **Debounce** (výchozí: 120s, konfigurovatelné)
- ✅ Když se okno otevře → počká X sekund
- ✅ Pokud je **stále otevřené** → přejde do VENT
- ✅ Pokud se **mezitím zavřelo** → ignoruje (pokračuje v topení)

### Periodický update:
- ✅ **Každých 30 sekund**
- ✅ Přesné časování vypnutí
- ✅ Kontrola timerů

## 🛠️ Error Handling

### Senzor offline:
```
Senzor unavailable > 2 min → ERROR stav
→ Vypne všechny TRV
→ Vrátí se do IDLE když se senzor vrátí
```

### TRV offline:
```
TRV unavailable > 5 min → ERROR stav
→ Vypne všechny TRV
→ Vrátí se do IDLE když se TRV vrátí
```

### Restart HA:
```
HA restartováno během topení → začne z IDLE
→ Zruší rozdělaný cyklus (bezpečnost)
→ Načte naučené parametry z úložiště
```

### Velmi dlouhé topení:
```
Topení > max_heating_duration → force stop
→ Přejde do IDLE
→ Označí cyklus jako nevalidní
```

## 🔧 Services

### `trv_regulator.reset_learned_params`

Resetuje naučené parametry pro vybranou místnost a spustí učení znovu.

**Parametry:**
- `entity_id` (volitelné): Climate entita (např. `climate.trv_regulator_loznice`)
- `room` (volitelné): Název místnosti (např. `loznice`)

**Příklad:**
```yaml
service: trv_regulator.reset_learned_params
data:
  entity_id: climate.trv_regulator_loznice
```

**Kdy použít:**
- Po výměně radiátoru
- Po výměně TRV hlavice
- Po změně podmínek v místnosti
- Když chcete začít učení od začátku

## 💾 Persistence

Naučené parametry se ukládají do `.storage/trv_regulator_learned_params.json`:

```json
{
  "kuchyn": {
    "avg_heating_duration": 1500,
    "time_offset": 180,
    "is_learning": false,
    "valid_cycles_count": 15,
    "last_learned": "2026-01-12T20:00:00",
    "avg_overshoot": 0.15,
    "history": [
      {
        "timestamp": 1736709600,
        "heating_duration": 1480,
        "overshoot": 0.3,
        "target": 22.0,
        "start_temp": 20.5,
        "stop_temp": 22.0,
        "max_temp": 22.3,
        "valid": true
      }
      // ... posledních 100 cyklů
    ]
  }
}
```

## ⚠️ Breaking Changes (verze 2.0.0)

### Kompletní přepsání z proporcionální regulace na ON/OFF

**Verze 2.0.0** přináší **zásadní breaking change**:

#### Co se změnilo:
- ❌ **Odstraněno:** Proporcionální regulace (gain × diff + offset)
- ❌ **Odstraněno:** Závislost na `heating_water_temp_entity`
- ❌ **Odstraněno:** Využití `current_temperature` z TRV hlavice
- ❌ **Odstraněno:** State `POST_VENT`
- ❌ **Odstraněno:** Senzory `gain`, `offset`, `oscillation`
- ✅ **Nové:** ON/OFF řízení (35°C / 5°C)
- ✅ **Nové:** Učící režim + prediktivní vypínání
- ✅ **Nové:** Adaptivní úprava time_offset
- ✅ **Nové:** Senzory `state`, `learning`, `last_cycle`, `history`

#### Migrace z verze 0.x:

**⚠️ POZOR: Nelze upgradeovat bez odebrání a opětovného přidání integrace!**

1. **Záloha konfigurace:**
   - Poznamenej si názvy místností a entity
   - Naučené parametry (gain/offset) **nelze převést**

2. **Odebrat starou integraci:**
   ```
   Nastavení → Zařízení a služby → TRV Regulator
   → Klikni na místnost → Odstranit
   ```

3. **Aktualizovat na verzi 2.0.0:**
   - HACS → TRV Regulator → Aktualizovat
   - Restart Home Assistant

4. **Přidat novou integraci:**
   ```
   Nastavení → Zařízení a služby → Přidat integraci → TRV Regulator
   ```
   - **NEZADÁVEJ** `heating_water_temp_entity` (už není v konfiguračním formuláři)
   - Nastav nové parametry učení (nebo ponech výchozí)

5. **Počkat na naučení:**
   - Prvních 10 cyklů bude systém **učit**
   - Sleduj `sensor.trv_regulator_{room}_learning`
   - Po naučení přejde do **prediktivního** režimu

#### Co očekávat po upgradu:

**První den:**
- Systém se učí → může být větší překmit (±0.5-1°C)
- Sleduj senzor `learning` - počítá validní cykly

**Po naučení:**
- Přesnější regulace díky predikci
- Minimální překmit (cílově ±0.1°C)
- Průběžné adaptivní učení

## 📝 Logování

Všechny důležité události jsou logovány do Home Assistant logu:

```
TRV [Kuchyn]: IDLE → HEATING
TRV [Kuchyn]: Started LEARNING cycle (3/10)
TRV [Kuchyn]: Heating stopped after 1450s, entering COOLDOWN
TRV [Kuchyn]: Cycle finished - duration=1450s, overshoot=0.25°C, valid=true
TRV [Kuchyn]: LEARNING COMPLETE! avg_duration=1440s, time_offset=45s
TRV [Kuchyn]: Adjusted time_offset: 45s → 57s (overshoot_error=0.20°C, mode=conservative)
```

Pro zobrazení logů:
```
Nastavení → Systém → Protokoly → Hledat "TRV"
```

## 🧪 Testování

### Test 1: Učící režim
1. Přidej novou místnost
2. Sleduj `sensor.trv_regulator_{room}_learning`
3. Počkej na 10 validních cyklů
4. Zkontroluj že `state` přešel z "learning" na "learned"

### Test 2: Prediktivní vypínání
1. Po naučení sleduj `sensor.trv_regulator_{room}_state`
2. V atributech `heating_remaining_seconds` by měl odpočítávat
3. TRV by mělo vypnout PŘED dosažením targetu

### Test 3: Krátké větrání
1. Otevři okno na 30 sekund
2. Zavři okno
3. Sleduj log → očekáváno: žádná změna (pod vent_delay)

### Test 4: Dlouhé větrání
1. Otevři okno na 3 minuty
2. Sleduj log → očekáváno: přechod do VENT (po 120s)
3. Pokud topilo → cyklus bude invalidní
4. Zavři okno
5. Sleduj log → okamžitě vyhodnotí teplotu

### Test 5: Kontinuální učení (klouzavý průměr)
1. V learned režimu sleduj `last_cycle` sensor
2. Zkontroluj `overshoot` každého cyklu
3. Sleduj jak se `time_offset` upravuje v `learning` sensoru
4. Parametry se postupně adaptují podle klouzavého průměru
5. Rychlost změn závisí na `learning_cycles_required`:
   - 5 cyklů = rychlé změny (20% vliv nového cyklu)
   - 10 cyklů = střední rychlost (10% vliv)
   - 20 cyklů = pomalé změny (5% vliv)

## 🐛 Řešení problémů

### TRV se nespínají
- Zkontroluj, že entity TRV jsou ve stavu `available`
- Ověř, že TRV podporují `climate.set_hvac_mode` a `climate.set_temperature`
- Zkontroluj logy pro chybové hlášky

### Systém přešel do ERROR
- Zkontroluj dostupnost teplotního senzoru
- Zkontroluj dostupnost TRV hlavic
- ERROR se automaticky vymaže když se entity vrátí

### Učení trvá dlouho
- Zkontroluj `sensor.trv_regulator_{room}_learning`
- Sleduj `valid_cycles` vs `required_cycles`
- Nevalidní cykly (okno, změna targetu) se nepočítají

### Velký překmit
- V learning režimu normální (až ±1°C)
- V learned režimu se automaticky adaptuje pomocí klouzavého průměru
- Pokud přetrvává:
  - Zkus snížit `learning_cycles_required` na 5 (rychlejší adaptace)
  - Nebo zvýš `desired_overshoot` na 0.2°C (tolerantnější)

## 🔄 Verzování

Integrace používá [sémantické verzování](https://semver.org/lang/cs/) (SemVer):

- **2.0.0** - Major breaking change (přechod na ON/OFF)
- **2.x.0** - Minor změny (nové funkce)
- **2.x.x** - Patch změny (bugfixy)

### Aktuální verze

Aktuální verzi najdeš v souboru `custom_components/trv_regulator/manifest.json`.

## 📄 Licence

MIT

## 👤 Autor

[@navratilpetr](https://github.com/navratilpetr)

## 🤝 Přispívání

Příspěvky jsou vítány! 🎉

- **Bug reports**: Použijte [Issue Tracker](https://github.com/navratilpetr/trv_regulator/issues)
- **Feature requests**: Navrhněte novou funkcionalitu pomocí [Feature Request](https://github.com/navratilpetr/trv_regulator/issues/new?template=feature_request.md)
- **Pull Requests**: Přečtěte si [CONTRIBUTING.md](CONTRIBUTING.md) pro detaily

### Development

```bash
# Klonování
git clone https://github.com/navratilpetr/trv_regulator.git
cd trv_regulator

# Instalace dev závislostí
pip install -r requirements-dev.txt

# Pre-commit hooks
pre-commit install

# Spuštění testů
pytest tests/

# Linting
ruff check custom_components/
black --check custom_components/
mypy custom_components/trv_regulator/
```

Více informací v [CONTRIBUTING.md](CONTRIBUTING.md).

## 🔒 Bezpečnost

Pokud najdete bezpečnostní zranitelnost, prosím **nehlaste ji veřejně**. Přečtěte si [SECURITY.md](SECURITY.md) pro instrukce.

## ⭐ Podpora

Pokud se ti integrace líbí, dej hvězdičku na GitHubu!
