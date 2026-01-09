# TRV Regulator

Custom integrace pro Home Assistant - řízení vytápění po místnostech pomocí TRV hlavic.

## ✨ Vlastnosti

- **Stavový automat:** Deterministické řízení pomocí stavů IDLE, HEATING, VENT, POST_VENT
- **Hystereze:** Přesná regulace ±0.3 °C (konfigurovatelná)
- **Větrání:** Automatické vypnutí topení při otevření okna
- **Multi-TRV:** Podpora více termostatických hlavic v jedné místnosti
- **Config Flow:** Kompletní konfigurace přes UI (bez YAML)

## 📦 Instalace

### HACS (doporučeno)
1. Otevři HACS v Home Assistantu
2. Přejdi na "Integrace"
3. Klikni na tři tečky vpravo nahoře → "Vlastní repozitáře"
4. Přidej URL: `https://github.com/navratilpetr/trv_regulator`
5. Kategorie: Integration
6. Klikni "Přidat"
7. Najdi "TRV Regulator" a nainstaluj
8. Restartuj Home Assistant

### Manuální instalace
1. Stáhni nejnovější release
2. Zkopíruj složku `custom_components/trv_regulator` do tvé Home Assistant konfigurace
3. Restartuj Home Assistant
4. Přidej integraci přes UI: Nastavení → Zařízení a služby → Přidat integraci → "TRV Regulator"

## 🔧 Konfigurace

### Povinné entity:
- **Senzor teploty** - aktuální naměřená teplota v místnosti
- **Cílová teplota** - požadovaná teplota místnosti
- **TRV hlavice** - jeden nebo více termostatů
- **Teplota topné vody** - aktuální teplota vody v systému

### Volitelné entity:
- **Okna** - binary senzory pro detekci větrání
- **Dveře** - binary senzory dveří (připraveno pro budoucí využití)
- **Hystereze** - rozsah teplot pro spínání (výchozí: 0.3 °C)
- **Zpoždění větrání** - čas do aktivace větrání (výchozí: 120 s)
- **Trvání post-ventilace** - ochranná doba po zavření okna (výchozí: 300 s)

## 📊 Stavový automat

```
IDLE ←→ HEATING
  ↕       ↕
VENT ← POST_VENT
```

### Stavy:
- **idle** - Topení vypnuto, čeká se
- **heating** - Aktivní topení
- **vent** - Větrání probíhá (TRV vypnuto)
- **post_vent** - Ochranná perioda po zavření okna

### Přechody:
- `IDLE → HEATING`: teplota ≤ cíl − hystereze
- `HEATING → IDLE`: teplota ≥ cíl + hystereze
- `* → VENT`: okno otevřeno déle než vent_delay
- `VENT → POST_VENT`: okno zavřeno
- `POST_VENT → IDLE/HEATING`: uplynutí post_vent_duration

## 📝 Logování

Všechny přechody mezi stavy jsou logovány do Home Assistant logu:

```
TRV [Kuchyn]: idle -> heating (temp 19.7, target 20.0)
TRV [Kuchyn]: heating -> vent (window opened)
TRV [Kuchyn]: vent -> post_vent (window closed)
TRV [Kuchyn]: post_vent ended, reevaluating -> heating
```

Pro zobrazení logů:
```
Nastavení → Systém → Protokoly → Hledat "TRV"
```

## 🧪 Testování

### Test 1: Základní regulace
1. Změň cílovou teplotu nad aktuální
2. Sleduj log → očekáváno: `idle -> heating`
3. Počkej na dosažení teploty
4. Sleduj log → očekáváno: `heating -> idle`

### Test 2: Krátké větrání
1. Otevři okno na 10 sekund
2. Zavři okno
3. Sleduj log → očekáváno: žádná změna (pod vent_delay)

### Test 3: Dlouhé větrání
1. Otevři okno na 3 minuty
2. Sleduj log → očekáváno: `heating -> vent` (po 120s)
3. Zavři okno
4. Sleduj log → očekáváno: `vent -> post_vent`
5. Počkej 5 minut
6. Sleduj log → očekáváno: `post_vent -> heating` (pokud je teplota nízká)

### Test 4: Ruční zásah
1. Vypni TRV ručně přes Home Assistant UI
2. Počkej na další update (max 30s)
3. Sleduj log → očekáváno: integrace přepíše ruční nastavení

## 🐛 Řešení problémů

### TRV se nespínají
- Zkontroluj, že entity TRV jsou ve stavu `available`
- Ověř, že TRV podporují `climate.set_hvac_mode` a `climate.set_temperature`
- Zkontroluj logy pro chybové hlášky

### Integrace se nespustí
- Ověř, že všechny povinné entity existují
- Zkontroluj Home Assistant logy pro chyby při načítání
- Zkontroluj verzi Home Assistant (minimální: 2024.1.0)

### Teploty se nečtou správně
- Ověř, že senzor teploty vrací číselnou hodnotu
- Zkontroluj jednotky (°C)
- Sleduj logy pro varování o nedostupných entitách

## 📄 Licence

MIT

## 👤 Autor

[@navratilpetr](https://github.com/navratilpetr)

## 🤝 Přispívání

Pull requesty jsou vítány! Pro větší změny nejdříve otevři issue pro diskuzi.

## ⭐ Podpora

Pokud se ti integrace líbí, dej hvězdičku na GitHubu!