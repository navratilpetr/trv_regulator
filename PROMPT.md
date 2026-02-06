# 📌 PROMPT – TRV Regulator (Home Assistant custom integration) - AKTUALIZOVÁNO

## 🤖 Role asistenta

Asistent funguje jako **technický expert** na Home Assistant, ESPHome, MQTT, Zigbee2MQTT, AppDaemon a Lovelace UI (Mushroom).

### 1. Ověřování

**Každou odpověď ověř podle aktuální oficiální dokumentace Home Assistanta.**

- Pro Lovelace UI používej **Mushroom** a ověřuj syntax podle:   
  https://github.com/piitaya/lovelace-mushroom/tree/main

- **Nepoužívej nic, co není v aktuální dokumentaci.**

### 2. Styl odpovědi

- **Stručně, přesně, bez nadbytečného vysvětlování.**

- Pokud dotaz není jednoznačný, **nejdříve se zeptej na upřesnění.**

- **Syntaxe musí odpovídat aktuální HA verzi.**

---
## 🚫 Co Copilot agent NESMÍ měnit

### Version Management
- ❌ **NIKDY neměnit** `custom_components/trv_regulator/manifest.json` version
- ⚠️ **CHANGELOG.md** - můžeš přidat sekci pro novou verzi, ale workflow to přepíše
- ℹ️ Version bump se děje AUTOMATICKY přes workflow `bump-version.yaml`

### CI/CD
- ❌ **NIKDY neměnit** `.github/workflows/*` soubory
- ❌ Výjimka: Pouze pokud uživatel EXPLICITNĚ požádá o změnu workflow

### Infrastructure files
- ⚠️ Změny v `README.md`, `PROMPT.md` jsou OK
- ⚠️ Ale NEVYŽADUJÍ version bump

---

## 🎯 Cíl

Navrhnout a implementovat custom integraci Home Assistantu `trv_regulator` pro řízení vytápění po místnostech pomocí TRV hlavic.  

Integrace nahrazuje YAML automatizace, ale musí dosáhnout minimálně stejné kvality regulace:  
- kolísání teploty ≤ ±0.3 °C
- žádné přetápění po zavření TRV
- korektní chování při větrání
- deterministický stavový automat (žádná magie)

---

## ⚠️ Zásadní rozhodnutí (NEMĚNIT)

### Integrace NEŘÍDÍ KOTEL
- kotel je řízen existující automatizací (on/off)
- tato integrace do řízení kotle nijak nezasahuje

### TRV hlavice se řídí výhradně ON/OFF
```python
ON  → hvac_mode: heat, temperature: 35
OFF → hvac_mode: heat, temperature: 5  # POZOR: režim "heat", ne "off"!
```
- Při každé změně TRV se vždy nastavuje **i hvac_mode**
- důvod: uživatel může TRV ručně vypnout v HA
- `hvac_mode: heat` místo `off` kvůli kompatibilitě se Zigbee TRV hlavicemi

### 🆕 TRV Mode Mismatch Tolerance (v3.0.17+)

**Některé TRV hlavice automaticky přepínají mode:**
- Příklad: Hlavice přepne z `heat` na `auto` i když teplota je správně nastavena
- **Integrace TO RESPEKTUJE:**
  - Pokud `temperature` sedí (35°C nebo 5°C) → command je **úspěšný**
  - Mode mismatch je zaznamenán ale **není považován za failure**
  - Automatická detekce `preferred_mode` (auto/heat) pro každou TRV
  
**Watchdog chování:**
- Kontroluje **JEN `temperature`**, ne `hvac_mode`
- Opraví jen pokud teplota NESEDÍ (±0.5°C tolerance)
- Mode mismatch → jen DEBUG log, žádná oprava

### Integrace řeší pouze místnosti
- Každá místnost = jeden `RoomController`
- `RoomController` je stavový automat
- Neexistuje žádná centrální regulace teploty

### Stav integrace musí být čitelný z logů
```
TRV [Kuchyn]: IDLE → HEATING
TRV [Kuchyn]: Started LEARNING cycle (3/10)
TRV [Kuchyn]: Heating stopped after 1450s, entering COOLDOWN
TRV [Kuchyn]: Cycle finished - duration=1450s, overshoot=0.25°C, valid=true
TRV [Kuchyn]: LEARNING COMPLETE! avg_duration=1440s, time_offset=45s
```

---

## 🏗️ Architektura

### Struktura souborů
```
custom_components/trv_regulator/
├── __init__.py          # Entry point, setup platform
├── manifest.json        # Integrace metadata
├── config_flow.py       # UI konfigurace (Config Flow + Options Flow)
├── const.py             # Konstanty (stavy, timeouty)
├── room_controller.py   # RoomController (stavový automat)
├── reliability_tracker.py    # 🆕 Reliability tracking (v3.0.17+)
├── coordinator.py       # DataUpdateCoordinator (sync s HA)
├── sensor.py            # Diagnostické senzory
├── services.yaml        # Definice services
└── strings.json         # Překlady UI
```

---

## 📊 Entity (konfigurovatelné přes UI)

### Povinné entity – místnost

#### `temperature_entity` (POVINNÁ, max 1)
- aktuální naměřená teplota v místnosti
- jediný vstup pro porovnání s cílovou teplotou
- typicky Zigbee teplotní senzor

#### `target_entity` (POVINNÁ, max 1)
- požadovaná teplota místnosti
- finální setpoint místnosti (žádné sčítání)
- typicky `input_number` nebo `number` entita

---

### Akční entity – místnost

#### `trv_entities` (POVINNÁ, 1..N)
- jedna nebo více TRV hlavic v místnosti
- každá TRV má vlastní enable/disable přepínač (přes Options Flow)
- regulátor řídí jen aktivní TRV
- všechny aktivní TRV se řídí synchronně

**Formát (od VERSION 3):**
```python
[
    {
        "entity": "climate.hlavice_loznice",
        "enabled": True,
        "last_seen_sensor": "sensor.hlavice_loznice_last_seen"  # volitelné (v3.0.21+)
    }
]
```

**Řízení TRV:**
```python
ON  → hvac_mode: heat, temperature: 35
OFF → hvac_mode: heat, temperature: 5
```

**Last seen monitoring (v3.0.21+):**
- Volitelný `last_seen_sensor` (device_class: timestamp)
- Detekuje vybité baterie a slabý Zigbee signál
- Kontroluje změnu last_seen před/po odeslání příkazu
- Rate limiting ERROR logů (max 1x/30min)

---

### Senzory otevření

#### `window_entities` (VOLITELNÁ, 0..N)
- okna nebo balkonové dveře určené pro větrání
- spouští VENT stav
- více oken = OR logika
- konfigurovatelný debounce (`window_open_delay`, výchozí 120s)

**POZNÁMKA:** `door_entities` byly odstraněny ve v3.0.0 a sloučeny s `window_entities`

---

### ❌ ODSTRANĚNÉ ENTITY (verze 3.0.0+)

#### ~~`heating_water_temperature_entity`~~ (ODSTRANĚNO)
- **již neexistuje** - byla odstraněna ve verzi 3.0.0
- důvod: ON/OFF režim ji nepotřebuje
- v promptu nesmí být zmíněna jako povinná

#### ~~`door_entities`~~ (ODSTRANĚNO)
- sloučeno s `window_entities`
- zachována zpětná kompatibilita v kódu

---

## 🆕 📊 Reliability Tracking (v3.0.17+)

### Smart Mode Detection
- **Mode mismatch tolerance** - některé TRV hlavice preferují `auto` mode místo `heat`
- Pokud TRV změní mode ale teplota SEDÍ → **není to failure!**
- Automatická detekce `preferred_mode` pro každou TRV
- Separátní tracking: `mode_mismatches` vs `command_failures`

### Watchdog Behavior
- Watchdog kontroluje **pouze teplotu**, ne hvac_mode
- Pokud teplota sedí (±0.5°C tolerance) → žádná oprava, jen DEBUG log
- Pokud teplota NESEDÍ → oprava + WARNING log + tracking
- **TRV_COMMAND_VERIFY_DELAY:** 15 sekund (čas na aplikaci příkazu)

### Reliability Metrics
- `commands_sent_total` - celkový počet příkazů
- `commands_failed_total` - reálné failures (ztracené příkazy, slabý signál)
- `mode_mismatches_total` - TRV změnila mode (není chyba!)
- `watchdog_corrections_total` - kolikrát watchdog opravil stav
- **Multi-window stats:** 1h, 24h, 7d, 30d

### Per-TRV Statistics
Pro místnosti s více hlavicemi (2+ TRV):
- Individuální metriky pro každou TRV
- `success_rate`, `signal_quality`, `preferred_mode`
- Viditelné v `trv_statistics` atributu reliability sensoru
- Umožňuje identifikovat problematickou hlavici

---

## 🆕 🔢 Sensory (v3.0.0+)

Integrace vytváří následující sensory pro každou místnost:

### State Sensor (`sensor.trv_regulator_{room}_state`)
- **State:** `idle`, `heating`, `cooldown`, `vent`, `error`
- **Atributy:** current_temp, target_temp, state_duration, heating_start, ...

### Reliability Sensor (`sensor.trv_regulator_{room}_reliability`)
- **State:** `strong`, `medium`, `weak` (podle reliability_rate)
- **Atributy:** 
  - `reliability_rate` (0-100%)
  - `signal_quality` (strong ≥98% / medium 90-98% / weak <90%)
  - `failed_commands_24h`, `watchdog_corrections_24h`
  - `mode_mismatches_total`
  - `command_history` (10 posledních - omezeno v3.0.18+)
  - `correction_history` (10 posledních - omezeno v3.0.18+)
  - `trv_statistics` (per-TRV data pro více hlavic)

### Learning Sensor (`sensor.trv_regulator_{room}_learning`)
- **State:** `learning` / `learned`
- **Atributy:** valid_cycles, avg_heating_duration, time_offset, is_learning, ...

### Stats Sensor (`sensor.trv_regulator_{room}_stats`)
- **State:** počet validních cyklů
- **Atributy:** agregované statistiky ze všech cyklů

### History Sensor (`sensor.trv_regulator_{room}_history`)
- **State:** celkový počet cyklů
- **Atributy:** `cycles` (20 posledních - omezeno v3.0.19+)

### Diagnostics Sensor (`sensor.trv_regulator_{room}_diagnostics`)
- **State:** `healthy` / `warning` / `error`
- **Atributy:** různé diagnostické info

### Last Cycle Sensor (`sensor.trv_regulator_{room}_last_cycle`)
- **State:** timestamp posledního cyklu
- **Atributy:** detaily posledního dokončeného topného cyklu

---

## 🆕 🔧 Sensor Atributy - Omezení velikosti (v3.0.18+)

### Reliability Sensor Optimalizace
- `command_history`: max **10 posledních** záznamů (bylo neomezené)
- `correction_history`: max **10 posledních** záznamů
- ~~`hourly_stats`, `daily_stats`~~: **odstraněno** z atributů (zůstává v JSON)
- **Důvod:** Home Assistant Recorder limit 16 KB pro state attributes

### History Sensor Optimalizace
- `cycles`: max **20 posledních** cyklů (bylo ~100)
- **Důvod:** Recorder limit 16 KB
- **Plná historie (100 cyklů)** zůstává v JSON persistence

### JSON Persistence
- Kompletní data uložena v `.storage/trv_regulator_learned_params.json`
- Načítá se při startu Home Assistantu
- Obsahuje všech 100 cyklů + kompletní reliability metriky
- Žádné omezení velikosti

---

## 🆕 🔔 Communication Problem Binary Sensor (v3.0.25+)

### Binary Sensor (`binary_sensor.trv_regulator_{room}_communication_problem`)

**State:** `on` / `off`

**Kdy je ON:**
- Poslední příkaz k TRV **SELHAL** (last_seen se nezměnil)
- Detekuje:
  - TRV offline (vybité baterie)
  - Slabý Zigbee signál
  - Fyzicky rozbitá hlavice
  - TRV zamrzlá v zapnutém/vypnutém stavu

**Kdy je OFF:**
- Poslední příkaz **USPĚL** (last_seen se změnil)
- Automatický reset při úspěchu

**Atributy:**
```yaml
problem_trvs:
  - entity_id: climate.hlavice_loznice
    last_failure_time: "2026-02-05T20:10:15"
    last_failure_reason: "no_response"
total_problem_trvs: 1
total_failures_24h: 5
```

**Filosofie:**
- ✅ **Jednoduchý** - jen ON/OFF (ne thresholdy)
- ✅ **Deterministický** - jasný stav
- ✅ **Flexibilní** - uživatel si vytvoří vlastní automatizace

**Use case:**
```yaml
# Jednoduchá notifikace
automation:
  - alias: "TRV - Komunikační problém"
    trigger:
      - platform: state
        entity_id: binary_sensor.trv_regulator_loznice_communication_problem
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ TRV Problém"
          message: "Zkontroluj baterie/signál"

# Pokročilá detekce přehřátí
automation:
  - alias: "TRV - Detekce zamrzlé hlavice"
    trigger:
      - platform: state
        entity_id: binary_sensor.trv_regulator_loznice_communication_problem
        to: "on"
        for: "00:05:00"
    condition:
      # Teplota roste (hlavice zamrzlá v ON)
      - condition: template
        value_template: >
          {% set current = states('sensor.teplota_loznice') | float %}
          {% set target = states('sensor.loznice_pozadovana') | float %}
          {{ current > target + 1.0 }}
    action:
      - service: notify.mobile_app
        data:
          title: "🔥 TRV zamrzlá v ON!"
          message: "Teplota roste navzdory příkazům"
```

---

## ⚠️ CRITICAL: Last_seen Sensor Requirements

**DŮLEŽITÉ:** Last_seen sensor MUSÍ být typu "FROM device", ne "TO device"!

### Zigbee2MQTT konfigurace:

```yaml
# Zigbee2MQTT configuration.yaml
advanced:
  elapsed: true  # ← CRITICAL! Povinné pro správnou detekci
```

**Co dělá `elapsed: true`:**
- Last_seen = timestamp posledního **PŘIJATÉHO** reportu od TRV
- Změní se POUZE když TRV aktivně reportuje
- ✅ Použitelné pro detekci offline hlavic

**Co dělá `elapsed: false` (ŠPATNĚ!):**
- Last_seen = timestamp **ODESLANÉHO** příkazu
- Změní se i když TRV neodpověděla
- ❌ NEPOUŽITELNÉ pro detekci!

### Testování:

```
1. Zjisti aktuální last_seen timestamp
2. Odpoj TRV z dosahu (nebo vypni baterie)
3. Pošli příkaz přes HA
4. Zkontroluj last_seen:
   ✅ Správně: last_seen se NEZMĚNIL (TRV neodpověděla)
   ❌ Špatně: last_seen se změnil (detekce nefunguje!)
```

**Pokud máš `elapsed: false`:**
- Nastav na `true` v Zigbee2MQTT konfiguraci
- Restart Zigbee2MQTT
- Znovu nakonfiguruj last_seen senzory v integraci

**Alternativy (pokud last_seen není dostupný):**
- Použij `linkquality` sensor (reportuje TRV)
- Použij `battery` sensor (reportuje TRV)
- Monitoring jejich `last_updated` timestamp

---

## 🤖 Stavový automat místnosti

### Stavy
```
IDLE       – topení vypnuto, čeká se
HEATING    – aktivní topení
COOLDOWN   – měří překmit po vypnutí topení (20 min)
VENT       – větrání probíhá, TRV vypnuto
ERROR      – senzor/TRV offline, TRV vypnuto
```

**⚠️ POST-VENT NENÍ STAV!**  
POST-VENT je **režim** (flag `_post_vent_mode`), který ovlivňuje chování během stavu `HEATING`.

---

### Regulace teploty (mimo větrání)

#### IDLE → HEATING
```python
temperature <= target - hysteresis
```

#### HEATING → COOLDOWN
```python
# Učící režim:
temperature >= target

# Naučený režim:
heating_elapsed >= (avg_heating_duration - time_offset)
```

#### COOLDOWN → IDLE
```python
cooldown_elapsed >= cooldown_duration  # výchozí 1200s (20 min)
```

---

### Větrání

#### Otevření okna (+ debounce)
```
window otevřeno > window_open_delay (120s)
→ HEATING/IDLE/COOLDOWN → VENT
→ TRV = OFF
```

#### Zavření okna během VENT
```
window zavřeno
→ VENT → IDLE
→ nastaví _post_vent_mode = True
```

#### POST-VENT režim (první topení po větrání)
```
IDLE → HEATING (s _post_vent_mode = True)
→ ignoruje naučený čas
→ topí až do dosažení targetu (jako LEARNING)
→ po ukončení: _post_vent_mode = False
→ tento cyklus je označen jako nevalidní (nepoužije se pro učení)
```

#### RECOVERY režim (velký teplotní rozdíl)

**Kdy se aktivuje:**
- Při přechodu do HEATING, pokud `(target - current) > recovery_threshold` (výchozí 1.0°C)
- Aktivuje se JEN při poklesu teploty (current < target), ne při přestřelení

**Chování:**
```
IDLE → HEATING (s recovery_mode = True)
→ ignoruje naučený čas
→ topí až do dosažení targetu (jako POST-VENT)
→ po ukončení: recovery_mode = False, návrat do LEARNED
→ tento cyklus JE validní (používá se pro učení)
```

**Rozdíl oproti POST-VENT:**
- **POST-VENT:** Cyklus je **nevalidní** (po větrání je situace nestandardní)
- **RECOVERY:** Cyklus je **validní** (normální topení, jen delší kvůli velkému ΔT)

**Use case:**
- Selhání TRV hlavice → velký pokles teploty
- Dlouhá absence → teplota klesla
- Po vypnutí topení přes noc

**Konfigurovatelné:**
- `recovery_threshold`: 0.5 - 3.0°C (výchozí 1.0°C)
- Settings → Integrace → TRV Regulator → Options

---

### Učící algoritmus

#### Fáze LEARNING (prvních N cyklů)
```python
if _is_learning:
    # Topí až do dosažení targetu
    if temperature >= target:
        stop_heating()
        enter_cooldown()
    
    # Měří heating_duration a overshoot
    # Po N validních cyklech vypočítá:
    #   - avg_heating_duration (průměr)
    #   - time_offset (predikce)
```

#### Fáze LEARNED (po naučení)
```python
if not _is_learning:
    # Vypíná PŘED dosažením targetu
    predicted_stop_time = avg_heating_duration - time_offset
    
    if heating_elapsed >= predicted_stop_time:
        stop_heating()
        enter_cooldown()
    
    # Průběžná adaptace time_offset podle skutečného překmitu
```

#### Validace cyklů
Cyklus je **nevalidní** pokud:
- byl přerušen otevřením okna
- změnila se cílová teplota během topení
- překmit > `max_valid_overshoot` (3.0°C)
- doba topení < `min_heating_duration` (180s)
- doba topení > `max_heating_duration` (7200s)
- cyklus byl v POST-VENT režimu

---

### Povinná pravidla

❌ nikdy netopit během VENT  
❌ nikdy použít POST-VENT cyklus pro učení  
✅ po zavření okna okamžitě vyhodnotit regulaci  
✅ žádný stav se nesmí zaseknout  
✅ více TRV respektuje enable/disable  
✅ COOLDOWN vždy měří překmit  
✅ 🆕 watchdog kontroluje jen teplotu (v3.0.17+)  
✅ 🆕 mode mismatch není považován za failure (v3.0.17+)  

---

## 📝 Logování (povinné)

Každý přechod musí být logován ve formátu:  

```
TRV [Kuchyn]: IDLE → HEATING
TRV [Kuchyn]: Started LEARNING cycle (3/10)
TRV [Kuchyn]: Heating stopped after 1450s, entering COOLDOWN
TRV [Kuchyn]: COOLDOWN → IDLE
TRV [Kuchyn]: Cycle finished - duration=1450s, overshoot=0.25°C, valid=true
TRV [Kuchyn]: LEARNING COMPLETE! avg_duration=1440s, time_offset=45s
```

### 🆕 Mode mismatch detection (v3.0.17+)
```
WARNING: TRV [loznice]: climate.hlavice_loznice mode differs 
(expected: heat, got: auto) but temperature is correct (5.0°C) - TRV prefers auto mode

DEBUG: Reliability [loznice]: Mode mismatch for climate.hlavice_loznice 
(expected: heat, got: auto, temp: 5.0°C) - TRV prefers auto
```

### 🆕 Watchdog behavior (v3.0.17+)
```
# Temperature mismatch - REAL problem:
WARNING: TRV [loznice]: STATE MISMATCH detected! 
Expected: 35°C, Actual: 5°C (mode: auto) - CORRECTING NOW

# Mode mismatch but temp OK - just DEBUG:
DEBUG: TRV [loznice]: climate.hlavice_loznice in auto mode 
(expected heat) but temperature correct (5.0°C)
```

---

## 🧪 Testovací scénáře

| Scénář | Očekávané chování |
|--------|-------------------|
| Teplota klesne pod `target − 0.3` | `IDLE → HEATING`, TRV ON |
| Teplota dosáhne targetu (LEARNING) | `HEATING → COOLDOWN`, TRV OFF |
| Predikovaný čas (LEARNED) | `HEATING → COOLDOWN` (před dosažením targetu) |
| COOLDOWN dokončen (20 min) | `COOLDOWN → IDLE` |
| Otevření okna na 10s | Žádná změna (< `window_open_delay`) |
| Otevření okna na 3 min | `→ VENT`, TRV OFF |
| Zavření okna během VENT | `VENT → IDLE`, nastaví `_post_vent_mode = True` |
| První topení po VENT | POST-VENT režim: topí do targetu, cyklus nevalidní |
| Ruční vypnutí TRV v HA | Při příštím update integrace přepíše |
| Více oken, jedno otevřené | Spustí větrání (OR logika) |
| TRV s `enabled: false` | Ignorována při řízení |
| 🆕 TRV změní mode na auto (v3.0.17+) | Pokud teplota sedí → success, jen DEBUG log |
| 🆕 TRV ztratí příkaz (v3.0.17+) | Watchdog opraví po 15s, zaznamená failure |

---

## ✅ UŽ IMPLEMENTOVÁNO (neměnit!)

- ✅ více místností najednou (multiple config entries)
- ✅ adaptivní offset (průběžná adaptace time_offset podle překmitu)
- ✅ reliability tracking (v3.0.17+)
- ✅ mode mismatch tolerance (v3.0.17+)
- ✅ per-TRV statistiky (v3.0.17+)
- ✅ sensor atributy optimalizovány pro Recorder (v3.0.18+, v3.0.19+)

---

## ❌ ZATÍM NEŘEŠIT (ale neblokovat architekturu)

- hydraulické vyvažování
- řízení kotle
- PID regulace (záměrně nepoužíváme - ON/OFF režim)

---

## ✅ Klíčová omezení

❌ žádný PID  
❌ žádná centrální regulace  
❌ žádné YAML automatizace  
❌ žádná `heating_water_temp_entity`  
✅ čistý stavový automat  
✅ maximální čitelnost chování  
✅ COOLDOWN vždy měří překmit  
✅ POST-VENT je režim, ne stav  
✅ 🆕 watchdog kontroluje jen teplotu (v3.0.17+)  
✅ 🆕 mode mismatch tolerance (v3.0.17+)  
✅ 🆕 sensor atributy pod 16 KB limitem (v3.0.18+, v3.0.19+)  

---

## 📚 Další dokumentace

- **Historie změn:** viz [CHANGELOG.md](CHANGELOG.md)
- **Instalace a konfigurace:** viz [README.md](README.md)
- **Dashboard příklady:** viz README.md - sekce Lovelace UI

---

## 🎯 Výsledek

Tento prompt slouží jako **jediný zdroj pravdy** pro:  
- generování kódu
- refaktoring
- testování
- dokumentaci

**Použití:**
1. Zkopíruj celý prompt
2. Vlož do AI asistenta
3. Požádej o: "Vygeneruj kompletní implementaci" nebo "Vytvoř PR s tímto kódem"
