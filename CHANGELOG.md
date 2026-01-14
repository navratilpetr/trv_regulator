# Changelog

Všechny významné změny v projektu budou dokumentovány v tomto souboru.

Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.0.0/),
a projekt dodržuje [sémantické verzování](https://semver.org/lang/cs/).

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

## [Unreleased]

### Přidáno
- **Proporcionální regulace** místo ON/OFF režimu
  - Výpočet cílové teploty: `(desired - room) × gain + offset + trv_local_temp`
  - Využití lokálního teploměru z TRV hlavice (`current_temperature`)
  - Konfigurovatelný gain (10-80, výchozí 40) a offset (-3.0 až +3.0, výchozí -0.1)
- **Diagnostické senzory** pro každou místnost:
  - `sensor.trv_{room}_gain` - aktuální gain hodnota
  - `sensor.trv_{room}_offset` - aktuální offset hodnota
  - `sensor.trv_{room}_oscillation` - oscilace teploty
  - `sensor.trv_{room}_trv_target` - cílová teplota poslaná na TRV
  - `sensor.trv_{room}_commands_total` - celkový počet příkazů
  - `sensor.trv_{room}_learned_gain` - naučený gain (placeholder pro ML)
- **Adaptivní učení** - základ pro budoucí ML optimalizaci
  - Historie teplot (1 hodina)
  - Výpočet oscilací
  - Placeholder pro doporučení úprav gain
- Nové parametry v config flow pro gain, offset a adaptivní učení

### Změněno
- ⚠️ **BREAKING:** Přepsána logika z ON/OFF (35°C/5°C) na proporcionální regulaci
- ⚠️ **BREAKING:** TRV nyní dostává dynamickou teplotu místo fixních hodnot
- Vylepšené logování s informacemi o proporcionální regulaci
- Aktualizovaná dokumentace s popisem proporcionální regulace a migračním průvodcem

### Opraveno
- Lepší predikce díky využití TRV lokálního teploměru
- Snížení oscilací díky proporcionální regulaci (±0.25-0.3°C místo ±1°C)

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
