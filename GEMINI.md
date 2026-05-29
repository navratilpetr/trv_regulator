# TRV Regulator - Projektový kontext

Tento soubor obsahuje klíčové informace o architektuře a fungování custom komponenty `trv_regulator` pro Home Assistant. Slouží jako kontext pro AI asistenta.

## Architektura a principy
- **Typ řízení:** ON/OFF řízení (termostat se chová jako přepínač 5°C / 35°C). Nepoužívá se PID ani proporcionální regulace.
- **Učení a predikce:** Jádrem je `RoomController`. Učí se tepelnou setrvačnost místnosti. Měří dobu vytopení a teplotní překmit po vypnutí. Po naučení (výchozí 10 cyklů) upravuje dobu topení tak, aby cílovou teplotu "trefil" s minimálním překmitem.
- **Stavový automat:**
  - `IDLE`: Teplota je dostatečná, TRV vypnuté.
  - `HEATING`: Probíhá topení, TRV zapnuté (35°C).
  - `COOLDOWN`: Topení vypnuto, měří se teplotní překmit.
  - `VENT`: Otevřené okno, TRV vypnuté.
  - `ERROR`: Selhala komunikace se senzorem nebo TRV.

## Pokročilé režimy (RoomController)
- **POST-VENT:** Automatický režim po zavření okna. První topný cyklus ignoruje naučené časy a topí až do dosažení cílové teploty. Neukládá se do historie učení.
- **RECOVERY:** Pokud teplota náhle klesne o více než nastavený `recovery_threshold` (např. >1°C), ignorují se naučené časy a rychle se dotápí. Cyklus se (na rozdíl od POST-VENT) zapisuje do učení.

## Detekce problémů (Reliability Tracker)
- **Modul `reliability_tracker.py`** detailně sleduje komunikaci s hlavicemi.
- Odlišuje opravdové chyby (TRV neodpovídá = `last_seen` senzor se nezměnil, nebo teplota nesedí) od akceptovatelných stavů (rozdílný `hvac_mode`, ale správná teplota).
- Automatický **Watchdog**: Pokud TRV nepřevezme správný stav, je vyslán opravný příkaz.

## Datová vrstva a ukládání
- Data a konfigurace pro uživatele se řeší výhradně přes **Config Flow** (UI). Nepoužívá se konfigurace přes YAML.
- **Persistence:** Historie cyklů a naučené parametry se ukládají lokálně do paměti Home Assistanta (`.storage/trv_regulator_learned_params.json`), aby přežily restart.

## Pravidla pro vývoj kódu
1. **Žádné synchronní čtení/zápis souborů:** Přístup na disk (např. v `.storage`) musí být volán přes `await self._hass.async_add_executor_job()`.
2. **Entity neblokují Home Assistant:** Veškeré updaty entit musí být debounceované (např. změna target teploty čeká 15s - `TARGET_DEBOUNCE_DELAY`).
3. **Logování:** Vyhýbáme se spamu v logu. Periodické updaty (např. loop v `TrvRegulatorCoordinator`) nesmí produkovat zbytečné logy.
4. **Čeština v logice/komentářích:** Projekt udržuje dokumentaci a část logování v angličtině, ale kód je komentován převážně česky (bez diakritiky) dle nastavení uživatele.
