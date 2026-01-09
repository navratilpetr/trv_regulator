# TRV Regulator

Custom integrace pro Home Assistant - **proporcionální regulace** vytápění po místnostech pomocí TRV hlavic.

## ✨ Vlastnosti

- **Proporcionální regulace:** Přesné řízení teploty pomocí gain/offset parametrů (±0.25-0.3 °C)
- **Využití TRV lokálního senzoru:** Měření teploty přímo u radiátoru pro lepší regulaci
- **Stavový automat:** Deterministické řízení pomocí stavů IDLE, HEATING, VENT, POST_VENT
- **Adaptivní učení:** Základ pro budoucí automatickou optimalizaci gain parametrů
- **Větrání:** Automatické vypnutí topení při otevření okna s ochrannou POST_VENT periodou
- **Multi-TRV:** Podpora více termostatických hlavic v jedné místnosti
- **Diagnostické senzory:** Sledování gain, offset, oscilací, cílové teploty a počtu příkazů
- **Config Flow:** Kompletní konfigurace přes UI (bez YAML)

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
- **Senzor teploty** - aktuální naměřená teplota v místnosti (externím senzorem)
- **Cílová teplota** - požadovaná teplota místnosti
- **TRV hlavice** - jeden nebo více termostatů (s lokálním teploměrem)
- **Teplota topné vody** - aktuální teplota vody v systému

### Volitelné entity a parametry:
- **Okna** - binary senzory pro detekci větrání
- **Dveře** - binary senzory dveří (připraveno pro budoucí využití)
- **Hystereze** - rozsah teplot pro přepínání stavů (výchozí: 0.3 °C)
- **Zpoždění větrání** - čas do aktivace větrání (výchozí: 120 s)
- **Trvání post-ventilace** - ochranná doba po zavření okna (výchozí: 300 s)
- **Gain** - proporcionální zesílení, 10-80 (výchozí: 40)
- **Offset** - offset pro jemné doladění, -3.0 až +3.0 (výchozí: -0.1)
- **Adaptivní učení** - aktivace adaptivního učení (výchozí: zapnuto)

## 🎯 Proporcionální regulace

Integrace používá **proporcionální algoritmus** místo jednoduchého ON/OFF režimu:

```python
# Výpočet cílové teploty pro TRV:
diff = desired_temp - room_temp
target = diff × gain + offset + trv_local_temp
# Omezení na rozsah 5-35°C
```

### Příklad:
- **Místnost:** 21.5°C
- **Požadovaná:** 22.0°C  
- **TRV lokální:** 24°C
- **Gain:** 40, **Offset:** -0.1

**Výpočet:**
```
diff = 22.0 - 21.5 = 0.5°C
target = 0.5 × 40 - 0.1 + 24 = 43.9°C → omezeno na 35°C
→ TRV topí naplno
```

Když teplota dosáhne 21.9°C:
```
diff = 0.1°C  
target = 0.1 × 40 - 0.1 + 24 = 27.9°C
→ TRV snižuje výkon (proporcionálně)
```

### Výhody oproti ON/OFF:
- ✅ Plynulá regulace místo oscilací
- ✅ Přesnost ±0.25-0.3°C (vs. ±1°C u ON/OFF)
- ✅ Využití lokálního teploměru TRV hlavice
- ✅ Lepší predikce díky měření setrvačnosti radiátoru
- ✅ Konfigurovatelné parametry pro každou místnost

## 📊 Diagnostické senzory

Pro každou místnost se automaticky vytvoří tyto senzory:

- `sensor.trv_{room}_gain` - aktuální gain hodnota
- `sensor.trv_{room}_offset` - aktuální offset hodnota  
- `sensor.trv_{room}_oscillation` - oscilace teploty v °C
- `sensor.trv_{room}_trv_target` - cílová teplota poslaná na TRV
- `sensor.trv_{room}_commands_total` - celkový počet odeslaných příkazů
- `sensor.trv_{room}_learned_gain` - naučený gain (budoucí ML)

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

## ⚠️ Breaking Changes (verze 0.1.0+)

### Změna z ON/OFF na proporcionální regulaci

**Verze 0.1.0** přináší zásadní změnu v regulační logice:

#### Co se změnilo:
- ❌ **Staré:** TRV bylo buď plně zapnuto (35°C) nebo vypnuto (5°C)
- ✅ **Nové:** TRV se nastavuje proporcionálně podle rozdílu teplot (5-35°C)

#### Migrace z verze 0.0.x:

1. **Aktualizuj integraci** na verzi 0.1.0+
2. **Restart Home Assistant**
3. **Překonfiguruj místnosti:** 
   - Otevři Nastavení → Zařízení a služby → TRV Regulator
   - Pro každou místnost klikni na "Konfigurovat"
   - Nastav **gain** a **offset** parametry:
     - **Výchozí hodnoty:** gain=40, offset=-0.1
     - **Pro různé místnosti** můžeš experimentovat s hodnotami 33-45 (gain)
   - Zapni **adaptivní učení** pro budoucí automatickou optimalizaci

4. **Sleduj senzory:**
   - `sensor.trv_{room}_oscillation` - měla by být <0.4°C
   - `sensor.trv_{room}_trv_target` - ukazuje, co se posílá na TRV
   - Pokud vidíš velké oscilace (>0.5°C), sniž gain

#### Doporučené nastavení pro začátek:
```yaml
Gain: 40
Offset: -0.1
Adaptivní učení: ANO
```

Po 24 hodinách provozu zkontroluj oscilaci a případně uprav gain.

### Nové povinné požadavky:

- **TRV hlavice musí podporovat** atribut `current_temperature`
  - Většina Zigbee2MQTT TRV hlavic (Moes, Tuya) to podporuje
  - Pokud TRV nemá tento atribut, použije se pokojová teplota jako fallback

### Nové entity:

Po upgradu se automaticky vytvoří 6 nových senzorů pro každou místnost (viz sekce Diagnostické senzory).

## 🧪 Testování

### Test 1: Proporcionální regulace
1. Nastav cílovou teplotu 1°C nad aktuální
2. Sleduj log → očekáváno: `idle -> heating` s cílovou teplotou ~35°C
3. Sleduj `sensor.trv_{room}_trv_target` - měl by ukazovat vysokou hodnotu
4. Jak se teplota blíží k cíli, target by měl postupně klesat
5. Při dosažení cíle → `heating -> idle`, TRV nastaveno na 5°C

### Test 2: Základní regulace
1. Změň cílovou teplotu nad aktuální
2. Sleduj log → očekáváno: `idle -> heating`
3. Počkej na dosažení teploty
4. Sleduj log → očekáváno: `heating -> idle`

### Test 3: Krátké větrání
1. Otevři okno na 10 sekund
2. Zavři okno
3. Sleduj log → očekáváno: žádná změna (pod vent_delay)

### Test 4: Dlouhé větrání
1. Otevři okno na 3 minuty
2. Sleduj log → očekáváno: `heating -> vent` (po 120s)
3. Zavři okno
4. Sleduj log → očekáváno: `vent -> post_vent`
5. Počkej 5 minut
6. Sleduj log → očekáváno: `post_vent -> heating` (pokud je teplota nízká)

### Test 5: Ruční zásah
1. Vypni TRV ručně přes Home Assistant UI
2. Počkej na další update (max 30s)
3. Sleduj log → očekáváno: integrace přepíše ruční nastavení

### Test 6: Diagnostické senzory
1. Zkontroluj, že se vytvořily všechny senzory pro místnost
2. `sensor.trv_{room}_oscillation` by měla být po pár hodinách <0.4°C
3. `sensor.trv_{room}_commands_total` by měl počítat všechny příkazy
4. Sleduj `sensor.trv_{room}_trv_target` při změnách teploty

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

## 🔄 Verzování

Integrace používá [sémantické verzování](https://semver.org/lang/cs/) (SemVer):

- **0.0.x** - Vývoj a testování (nestabilní)
- **0.x.0** - Alpha/Beta verze (funkční, ale s možnými změnami)
- **1.0.0+** - Stabilní produkční verze

### Automatické verzování

Při merge pull requestu se verze automaticky zvýší podle labelu:

- `breaking` - zvýší MAJOR verzi (např. 0.1.0 → 1.0.0)
- `feature` - zvýší MINOR verzi (např. 0.1.2 → 0.2.0)
- Bez labelu - zvýší PATCH verzi (např. 0.1.2 → 0.1.3)

### Aktuální verze

Aktuální verzi najdeš v souboru `custom_components/trv_regulator/manifest.json`.

Pro update v Home Assistant:
1. Stáhni nejnovější verzi z GitHubu
2. Restartuj Home Assistant
3. Zkontroluj Nastavení → Zařízení a služby → TRV Regulator

## 📄 Licence

MIT

## 👤 Autor

[@navratilpetr](https://github.com/navratilpetr)

## 🤝 Přispívání

Pull requesty jsou vítány! Pro větší změny nejdříve otevři issue pro diskuzi.

## ⭐ Podpora

Pokud se ti integrace líbí, dej hvězdičku na GitHubu!