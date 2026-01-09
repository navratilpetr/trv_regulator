# Changelog

Všechny významné změny v projektu budou dokumentovány v tomto souboru.

Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.0.0/),
a projekt dodržuje [sémantické verzování](https://semver.org/lang/cs/).

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
  - `sensor.trv_{room}_commands_today` - počet příkazů
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

[Unreleased]: https://github.com/navratilpetr/trv_regulator/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/navratilpetr/trv_regulator/releases/tag/v0.0.1
