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

**Řízení TRV:**
```python
ON  → hvac_mode: heat, temperature: 35
OFF → hvac_mode: heat, temperature: 5
```

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

---

## ❌ ZATÍM NEŘEŠIT (ale neblokovat architekturu)

- více místností najednou (už funguje přes multiple config entries)
- dveře jako samostatný vstup (sloučeno s okny)
- adaptivní učení - PID (existuje adaptivní offset)
- hydraulické vyvažování
- řízení kotle

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