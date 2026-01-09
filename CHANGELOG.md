# Changelog

Všechny významné změny v projektu budou dokumentovány v tomto souboru.

Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.0.0/),
a projekt dodržuje [sémantické verzování](https://semver.org/lang/cs/).

## [Unreleased]

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
