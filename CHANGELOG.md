# Changelog

Všechny významné změny v projektu budou dokumentovány v tomto souboru.

Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.0.0/),
a projekt dodržuje [sémantické verzování](https://semver.org/lang/cs/).

## [Unreleased]

## [3.0.18] - 2026-02-04

### Opraveno
- 🐛 **Recorder warnings pro reliability sensors**
  - Omezení `command_history` na 10 záznamů (bylo 100)
  - Omezení `correction_history` na 10 záznamů (bylo 100)
  - Odstranění `hourly_stats` a `daily_stats` z atributů (zůstává v JSON)
  - **Důvod:** Atributy překračovaly 16 KB limit a neukládaly se do databáze
- 🐛 **CHANGELOG duplicita** - verze 3.0.17 byla tam dvakrát
  - Opraveno: Vyčištěn CHANGELOG, odstraněna duplicita

### Změněno
- ⚙️ **Vylepšen bump-version.yaml workflow**
  - Použit awk místo sed pro bezpečnější náhradu
  - Přidána kontrola existující verze v CHANGELOG
  - Prevence duplicitních verzí

### Přidáno
- 📝 **CHANGELOG pravidla pro Copilot agenty**
  - Dokumentace v `.github/COPILOT_CHANGELOG_RULES.md`
  - Instrukce jak správně upravovat CHANGELOG

## [3.0.17] - 2026-02-04

### Opraveno
- 🐛 **False positive failures kvůli mode changes**
  - Opraveno: TRV které preferují `auto` mode místo `heat` již nejsou považovány za selhání
  - Watchdog nyní kontroluje pouze teplotu, ne hvac_mode
  - Přidána detekce preferovaného mode pro každou TRV
  - Mode mismatches jsou sledovány separátně (ne jako failures)
  - Failure rate nyní odráží jen REÁLNÉ problémy (ztracené příkazy, offline TRV)
  - **Důvod:** TRV hlavice typu `climate.hlavice_loznice` automaticky přepínají z `heat` na `auto` mode, i když teplota je správně nastavena

### Změněno
- ⚙️ **TRV_COMMAND_VERIFY_DELAY zvýšeno z 5s na 15s**
  - Větší jistota že TRV stihla přijmout a zpracovat příkaz
  - Méně false positives při přechodném výpadku Zigbee komunikace
  - Vhodné pro TRV se slabším signálem

### Přidáno
- 📊 **Smart mode detection** - automatická detekce preferovaného hvac_mode každé TRV
  - Nová metrika `mode_mismatches_total` - počet mode změn (ne failures!)
  - Per-TRV atribut `preferred_mode` - detekovaný preferovaný mode (auto/heat/off)
  - Per-TRV atribut `mode_mismatches` - kolikrát TRV změnila mode

### Technické změny
- Rozšířen `const.py`:
  - `TRV_COMMAND_VERIFY_DELAY = 15` sekund (zvýšeno z 5s)
  - `FAILURE_REASON_TEMP_MISMATCH` - teplota nesedí (REÁLNÉ selhání)
  - `FAILURE_REASON_MODE_MISMATCH` - mode nesedí, teplota OK (TRV preference)
  - `FAILURE_REASON_OFFLINE` - TRV offline/unavailable
  - České komentáře bez diakritiky (encoding compatibility)
- Upravena metoda `_set_all_trv()` v `room_controller.py`:
  - Tolerantní verifikace - kontroluje teplotu, ne mode
  - Volá `mode_mismatch()` místo `command_failed()` pro mode changes
- Upravena metoda `_verify_trv_state()` v `room_controller.py`:
  - Watchdog opravuje jen temperature mismatches
  - Mode mismatches pouze loguje (DEBUG level)
- Nová metoda `mode_mismatch()` v `reliability_tracker.py`
- Rozšířena persistence o `mode_mismatches_total`, `per_trv_mode_mismatches`, `per_trv_preferred_mode`

## [3.0.16] - 2026-02-04

### Přidáno
- 📊 **TRV Reliability Tracking** - Komprehenzivní sledování spolehlivosti TRV komunikace
  - Multi-window statistiky (1h / 24h / 7d / 30d)
  - Per-TRV reliability sensory pro každou hlavici
  - Aggregate reliability sensor pro celou místnost
  - Automatická detekce slabého Zigbee signálu
  - Signal quality classification (strong ≥98%, medium ≥90%, weak <90%)
  - Trend analysis (improving / stable / deteriorating)
  - Command history (100 posledních příkazů)
  - Correction history (100 posledních watchdog oprav)
  - Hourly statistics (720 záznamů = 30 dní)
  - Daily statistics (30 dní historie)

### Sensory
- `sensor.trv_regulator_{room}_reliability` - aggregate reliability sensor
  - State: weak / medium / strong
  - Atributy: reliability_rate, failed_commands_24h, watchdog_corrections_24h, signal_trend, trv_statistics
- `sensor.trv_regulator_{room}_trv_{N}_reliability` - per-TRV reliability sensor
  - Individuální metriky pro každou TRV hlavici
  - Success rate, signal quality, commands sent/failed

### UI Vizualizace
- Ready-to-use Lovelace konfigurace v `examples/` folderu
  - `lovelace_gauge.yaml` - vizuální gauge indikátor
  - `lovelace_complete.yaml` - kompletní dashboard
  - `lovelace_apexcharts.yaml` - trend grafy (vyžaduje HACS ApexCharts Card)

### Technické změny
- Nový soubor `reliability_tracker.py` - hlavní tracking logika
- Nový soubor `reliability_sensors.py` - per-TRV sensory
- Rozšířen `room_controller.py` o reliability tracking hooks
- Rozšířen `sensor.py` o aggregate reliability sensor
- Rozšířen `const.py` o reliability thresholdy a konstanty
- Rozšíření JSON storage o `reliability_metrics`
- Full events persistence (30 dní history)
- Automatický cleanup starých událostí

## [3.0.15] - 2026-02-03

### Přidáno
- 🛡️ **TRV State Verification** - Ověření stavu TRV 5s po odeslání příkazu
  - Detekuje ztracené příkazy kvůli slabému Zigbee signálu
  - Loguje ERROR pokud TRV neprovedla příkaz
- 🔍 **TRV Watchdog** - Pravidelná kontrola stavu TRV každých 30s
  - Detekuje nesoulad mezi očekávaným a skutečným stavem TRV
  - Automaticky opravuje TRV které zůstaly v nesprávném režimu
  - Zabraňuje přetápění při ztrátě komunikace

### Opraveno
- 🐛 **Kritická chyba: TRV zůstávají topit při slabém signálu**
  - Opraveno: TRV se slabším signálem někdy nezareagují na příkaz OFF
  - Systém nyní automaticky detekuje a opravuje nesoulad
  - Přidána konstanta `TRV_COMMAND_VERIFY_DELAY = 5` sekund

### Technické změny
- Nová metoda `_verify_trv_state()` v `RoomController`
- Rozšířená metoda `_set_all_trv()` o post-command verifikaci
- Import `TRV_COMMAND_VERIFY_DELAY` z `const.py`

## [3.0.14] - 2026-01-16

### Opraveno
- 🐛 **Duplicitní názvy entit** - odstraněna duplicita názvu místnosti v entity_id
  - Entity_id změněno z `sensor.trv_regulator_kuchyn_trv_kuchyn_diagnostics` na `sensor.trv_regulator_kuchyn_diagnostics`
  - Odstraněn název místnosti z `_attr_name` u všech senzorů (State, Learning, Last Cycle, History, Stats, Diagnostics)
  - HA automaticky přidá název místnosti z device name díky `has_entity_name = True`

### Dokumentace
- ✅ **Aktualizována dokumentace** - všechny reference na entity_id opraveny
  - Změněno `sensor.trv_{room}_*` na `sensor.trv_regulator_{room}_*`
  - Dokumentace nyní odpovídá skutečným názvům entit

## [3.0.13] - 2026-01-16

### Opraveno
- 🐛 **ValueError při vytváření diagnostics sensoru**
  - Opraveno: `entity_category` nyní používá `EntityCategory.DIAGNOSTIC` enum místo stringu `"diagnostic"`
  - Diagnostics sensor se nyní správně vytváří a je viditelný v UI
  - Přidán import `from homeassistant.helpers.entity import EntityCategory`

## [3.0.12] - 2026-01-16

### Opraveno
- 🐛 **Chyba při vytváření sensorů** - opraven problém "Error adding entity None"
  - Přidáno `device_info` do `TrvBaseSensor` a `TrvSummarySensor`
  - Diagnostics sensor je nyní správně viditelný jako diagnostic entity
  - Všechny senzory jsou správně seskupené pod zařízením v UI

## [3.0.11] - 2026-01-15

### Přidáno
- 📊 **Statistické senzory**
  - `sensor.trv_regulator_{room}_stats` - kompletní statistiky pro každou místnost
    - Celkové/validní/nevalidní cykly, úspěšnost
    - Průměrná/min/max doba topení
    - Průměrný/min/max překmit
    - První/poslední cyklus, dny v provozu, průměr cyklů za den
  - `sensor.trv_regulator_summary` - přehled všech místností
    - Seznam místností se stavem a statistikami
    - Celkový počet cyklů
    - Počet naučených/učících se místností

- 📈 **Long-term statistiky (měsíční agregace)**
  - Automatické ukládání měsíčních statistik do JSON
  - Průměrná doba topení, překmit, počet cyklů za měsíc
  - Historie až 24 měsíců (2 roky)
  - Automatické mazání starších záznamů

- 🔍 **Diagnostic sensor**
  - `sensor.trv_regulator_{room}_diagnostics` - diagnostické informace
  - Stav všech komponent (senzory teploty/targetu/okna, TRV hlavice)
  - Status (online/offline), poslední aktualizace
  - Statistiky invalidovaných cyklů podle důvodu
  - Aktuální konfigurace místnosti
  - Celkový health status (healthy/warning/error)

### Technické detaily
- Nové sensor třídy v `sensor.py`: TrvStatsSensor, TrvSummarySensor, TrvDiagnosticsSensor
- Měsíční agregace v metodě `_aggregate_monthly_stats()` v RoomController
- Rozšíření JSON persistence o `monthly_stats`
- Summary sensor sdílený napříč všemi místnostmi
- Diagnostic sensor s entity_category="diagnostic"

## [3.0.9] - 2026-01-15

### Změněno
- ⚙️ **TRV_OFF režim změněn z "off" na "heat"**
  - Režim změněn z `{"hvac_mode": "off", "temperature": 5}` na `{"hvac_mode": "heat", "temperature": 5}`
  - Lepší kompatibilita s TRV hlavicemi které nepodporují režim "off" (např. některé Zigbee termostatické hlavice)
  - Funkčně ekvivalentní - teplota 5°C vypne topení

### Přidáno
- ✅ **POST-VENT režim** - inteligentní dotopení po větrání
  - Po zavření okna první topný cyklus ignoruje naučený čas
  - Topí až do dosažení cílové teploty (stejně jako v LEARNING režimu)
  - Řeší problém nedotopení po větším poklesu teploty během větrání
  - V historii označeno atributem `"post_vent": true`
  - POST-VENT cykly nejsou použity pro učení (jsou považovány za nevalidní)
  - Bezpečnostní limit `max_heating_duration` stále platí

- 🎛️ **Options Flow - výběr aktivních TRV hlavic**
  - Možnost zapnout/vypnout jednotlivé TRV hlavice přes UI
  - Multi-select v nastavení integrace (Nastavení → Integrace → TRV Regulator → Možnosti)
  - Backend logika již existovala, nyní přidáno UI
  - Minimálně jedna TRV hlavice musí zůstat aktivní

- 🔧 **Service pro reset naučených parametrů**
  - Nová service `trv_regulator.reset_learned_params`
  - Umožňuje manuálně smazat naučené parametry a začít učení znovu
  - Užitečné po výměně radiátoru nebo TRV hlavice
  - Podporuje `entity_id` nebo `room` parametr
  - Použití: `service: trv_regulator.reset_learned_params` s `entity_id: climate.trv_regulator_loznice`

### Technické detaily
- Přidán flag `_post_vent_mode` v RoomController
- Automatická detekce přechodu z VENT → HEATING stavu
- POST-VENT cykly jsou automaticky invalidovány v `_is_cycle_valid()`
- Service registrována v `async_setup_entry()`
- Nová metoda `reset_learned_params()` v RoomController
- Multi-select v Options Flow s validací minimálního počtu aktivních TRV
- Podpora pro dict formát TRV entities s `enabled` flagem
- Vytvořen soubor `services.yaml` s definicí služby

## [3.0.8] - 2026-01-15

### Technické
- Automatický bump verze (GitHub Actions)

## [3.0.7] - 2026-01-14

### Technické
- Automatický bump verze (GitHub Actions)

## [3.0.6] - 2026-01-14

### Přidáno
- ✅ **Post-restart safety check** - po restartu Home Assistant automaticky nastaví všechny TRV do bezpečného stavu (OFF)
  - Vyčistí rozpracované topné cykly pro zajištění konzistence
  - Chrání proti riziku přetopení v případě, že hlavice zůstaly zapnuté během restartu
  - Loguje bezpečnostní akce pro lepší diagnostiku
  - Přidána metoda `reset_cycle_state()` v `RoomController`
- ✅ **Async file I/O** - všechny operace se soubory nyní probíhají asynchronně
  - Odstraněny blocking calls v Home Assistant event loopu
  - Použití `homeassistant.util.json.load_json` pro čtení
  - Použití standardního `json.dump()` v async wrapperu pro zápis
  - Metody `_load_learned_params()` a `_save_learned_params()` jsou nyní async
  - Lepší výkon a dodržení Home Assistant best practices

### Opraveno
- 🐛 **Blocking I/O warnings** - vyřešeno varování "Detected blocking call to open() inside the event loop"
  - Čtení: `await async_add_executor_job(load_json, path)`
  - Zápis: `await async_add_executor_job(_write_json)`
- 🐛 **Bezpečnostní riziko po restartu** - opravena situace kdy TRV hlavice mohly zůstat v režimu topení (35°C) po restartu HA, zatímco systém byl v IDLE stavu
- 🐛 **Import error** - opraven pokus o import neexistující funkce `save_json` z `homeassistant.util.json`
- 🐛 **Konzistence stavu** - zajištěno že po restartu je stav TRV hlavic konzistentní se stavem regulátoru

### Technické změny
- Import změněn z `from homeassistant.util.json import load_json, save_json` na `import json` + `from homeassistant.util.json import load_json`
- Volání `_load_learned_params()` v `async_setup_entry` nyní s `await`
- Volání `_save_learned_params()` v `_finish_cooldown()` nyní s `await`
- Bezpečnostní reset TRV do OFF stavu ihned po startu integrace

## [3.0.2] - 2026-01-13

### Opraveno
- 🐛 **Options Flow nefunkční** - opravena chyba "AttributeError: property 'config_entry' has no setter"
  - Odstraněn problematický `__init__` v `TrvRegulatorOptionsFlow`
  - Použit modernější přístup - parent class se postará o inicializaci
  - Options flow nyní správně funguje v UI (Nastavení → Možnosti ⚙️)

### Změněno
- ⚙️ **TRV_ON teplota změněna z 30°C na 35°C**
  - Vyšší teplota zajišťuje spolehlivější zapnutí topení
  - Mode "heat" je vždy explicitně posílán spolu s teplotou
  - Testováno a ověřeno v produkci

## [3.0.0] - 2026-01-12

### ⚠️ BREAKING CHANGES

Tato verze přináší **kompletní přepsání regulační logiky** z proporcionální regulace na ON/OFF řízení s adaptivním učením.

**VYŽADUJE** odebrání a opětovné přidání integrace! Nelze upgradeovat bez opětovné konfigurace.

### Odstraněno
- ❌ **Proporcionální regulace** - odstraněny parametry `gain` a `offset`
- ❌ **heating_water_temp_entity** - již není potřeba teplota vody z kotle
- ❌ **current_temperature z TRV** - již se nepoužívá lokální teplota z hlavice
- ❌ **POST_VENT stav** - odstraněn parametr `post_vent_duration`
- ❌ **door_entities** - sloučeno s `window_entities` (zachována zpětná kompatibilita)
- ❌ **Staré senzory:**
  - `sensor.trv_{room}_gain`
  - `sensor.trv_{room}_offset`
  - `sensor.trv_{room}_oscillation`
  - `sensor.trv_{room}_trv_target`
  - `sensor.trv_{room}_commands_total`
  - `sensor.trv_{room}_learned_gain`

### Přidáno
- ✅ **ON/OFF řízení:**
  - TRV zapnutá: 30°C
  - TRV vypnutá: 5°C
  - Žádná proporcionální regulace
- ✅ **Učící režim (LEARNING):**
  - Prvních X cyklů (výchozí: 10) topí do dosažení targetu
  - Měří `heating_duration` a `overshoot`
  - Validuje cykly (nebyl přerušen oknem, změnou targetu, atd.)
  - Po nasbírání validních cyklů vypočítá `avg_heating_duration` a `time_offset`
- ✅ **Prediktivní vypínání (LEARNED):**
  - Vypíná podle času: `avg_heating_duration - time_offset`
  - NEčeká na dosažení targetu (predikce)
  - Minimalizuje překmit
- ✅ **Adaptivní učení:**
  - **Conservative režim:** Postupné úpravy (20% korekce)
  - **Aggressive režim:** Rychlé úpravy (±1-2 min)
  - Průběžná úprava `time_offset` podle skutečného překmitu
- ✅ **Nové stavy:**
  - `STATE_COOLDOWN` - měří překmit po vypnutí (20 min)
  - `STATE_ERROR` - senzor/TRV offline
- ✅ **Debounce:**
  - Target: 15 sekund (ignoruje rychlé změny slideru)
  - Okna: konfigurovatelný (výchozí: 120s) - **přejmenováno z `vent_delay` na `window_open_delay`**
- ✅ **Error handling:**
  - Senzor offline > 2 min → ERROR
  - TRV offline > 5 min → ERROR
  - Topení > max_duration → force stop
- ✅ **Persistence:**
  - Ukládá historii 100 cyklů do `.storage/trv_regulator_learned_params.json`
  - Načítá při startu HA
- ✅ **Nové parametry konfigurace:**
  - `learning_speed` - conservative / aggressive (výchozí: conservative)
  - `learning_cycles_required` - 5-30 cyklů (výchozí: 10)
  - `desired_overshoot` - 0.0-0.5°C (výchozí: 0.1°C)
  - `min_heating_duration` - 60-600s (výchozí: 180s)
  - `max_heating_duration` - 900-10800s (výchozí: 7200s)
  - `max_valid_overshoot` - 1.0-5.0°C (výchozí: 3.0°C)
  - `cooldown_duration` - 600-1800s (výchozí: 1200s)
  - `window_open_delay` - 30-600s (výchozí: 120s) - **přejmenováno z `vent_delay`**
- ✅ **Nové senzory:**
  - `sensor.trv_regulator_{room}_state` - stav automatu + atributy (current_temp, target_temp, heating_elapsed/remaining)
  - `sensor.trv_regulator_{room}_learning` - stav učení + parametry (valid_cycles, avg_duration, time_offset, avg_overshoot)
  - `sensor.trv_regulator_{room}_last_cycle` - poslední cyklus (heating_duration, overshoot, start/stop/max temp, valid)
  - `sensor.trv_regulator_{room}_history` - historie až 100 cyklů v atributech
- ✅ **Options flow:**
  - Všechny parametry lze měnit po konfiguraci bez odebrání integrace

### Změněno
- ⚙️ **Update interval:** 30 sekund (pevně, změněno z 10s)
- ⚙️ **TRV_ON teplota:** 30°C
- ⚙️ **TRV_OFF teplota:** 5°C
- ⚙️ **Stavový automat:** IDLE, HEATING, COOLDOWN, VENT, ERROR (změněno z IDLE, HEATING, VENT, POST_VENT)
- ⚙️ **Parametr `vent_delay`** přejmenován na **`window_open_delay`** (zachována zpětná kompatibilita)

### Migrace z verze 0.x nebo 2.x

1. **Záloha:** Poznamenej si názvy místností a entity
2. **Odebrat:** Odstraň staré konfigurace TRV Regulator
3. **Update:** Aktualizuj na verzi 3.0.0 přes HACS
4. **Restart:** Restartuj Home Assistant
5. **Přidat:** Přidej integraci znovu (NEZADÁVEJ `heating_water_temp_entity`, `gain`, `offset`)
6. **Naučit:** Počkej na naučení (prvních 10 cyklů)

**Poznámka:** Naučené parametry z verze 0.x nebo 2.x (gain/offset) **nelze převést** na nový systém.


## [0.0.1] - 2026-01-09

### Přidáno
- Základní implementace stavového automatu (IDLE, HEATING, VENT, POST_VENT)
- Config flow pro konfiguraci přes UI
- Podpora více TRV hlavic v místnosti
- Detekce větrání s konfigurovatelným zpožděním
- POST_VENT ochranná perioda po zavření okna
- Hysterezní regulace teploty (výchozí ±0.3°C)
- Logování všech stavových přechodů
- České překlady v UI
- Podpora pro HACS instalaci

### Poznámky
- První testovací verze - **NESTABILNÍ**
- Vyžaduje důkladné testování před produkčním použitím

[2.0.0]: https://github.com/navratilpetr/trv_regulator/releases/tag/v2.0.0
[Unreleased]: https://github.com/navratilpetr/trv_regulator/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/navratilpetr/trv_regulator/releases/tag/v0.0.1
