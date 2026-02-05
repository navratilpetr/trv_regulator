# TRV Regulator

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
  
- 🔥 **RECOVERY režim** - Rychlé dotopení při velkém poklesu teploty
  - Automaticky detekuje velký teplotní rozdíl (>1°C)
  - Topí až do dosažení cíle místo použití naučeného času
  - Řeší rychlé dotopení po selhání hlavice nebo dlouhé absenci
  - Na rozdíl od POST-VENT je cyklus validní pro učení
  
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
- **Last seen sensory** - timestamp senzory pro detekci vybité baterie/slabého signálu (volitelné, od v3.0.21)
  - Formát: `sensor.{název_trv}_last_seen` s `device_class: timestamp`
  - Detekuje kdy TRV přestane reagovat na příkazy
  - Automaticky rozlišuje slabou baterii vs slabý Zigbee signál
  - Lze přiřadit při instalaci nebo později v Nastavení → Možnosti
  - Pokud není nakonfigurován, používá se jen temperature verification
- **Hystereze** - rozsah teplot pro přepínání stavů (0.0-2.0°C, výchozí: 0.3°C)
- **Zpoždění větrání** - čas do aktivace větrání (30-600s, výchozí: 120s)

### Parametry učení

| Parametr | Rozsah | Výchozí | Popis |
|----------|--------|---------|-------|
| Počet cyklů pro učení | 5-30 | 10 | Velikost klouzavého průměru |
| Požadovaný překmit | 0.0-0.5°C | 0.1°C | Cílový překmit |
| Min. doba topení | 60-600s | 180s | Minimální validní čas |
| Max. doba topení | 900-10800s | 7200s | Maximální validní čas |
| Max. validní překmit | 1.0-5.0°C | 3.0°C | Limit pro validaci |
| Doba cooldown | 600-1800s | 1200s | Jak dlouho měřit překmit |
| Recovery threshold | 0.5-3.0°C | 1.0°C | Aktivace RECOVERY režimu |

### RECOVERY režim

Když teplota klesne o více než `recovery_threshold` (výchozí 1.0°C), systém automaticky přepne do RECOVERY režimu:

**Scénář:**
```
Teplota klesla z 22°C na 20°C (např. selhání hlavice)
↓
Rozdíl 2°C > threshold 1.0°C → RECOVERY mode
↓
Topí až do dosažení 22°C (ignoruje naučený čas)
↓
Cíl dosažen → návrat do normálního LEARNED režimu
```

**Výhody:**
- ✅ Rychlé dotopení po selhání
- ✅ Rychlé dotopení po dlouhé absenci
- ✅ Cyklus se používá pro učení (na rozdíl od POST-VENT)
- ✅ Konfigurovatelný threshold přes UI

## 🎯 Jak to funguje

Integrace používá **ON/OFF řízení** s prediktivním vypínáním:

### Učící fáze (prvních 10 cyklů)
- Systém měří jak dlouho trvá ohřát místnost na cílovou teplotu
- Měří překmit (o kolik teplota přestřelí cíl)
- Po 10 validních cyklech vypočítá optimální čas vypnutí

### Naučený režim
- Vypíná topení PŘED dosažením cíle (podle naučeného času)
- Minimalizuje překmit na ~0.1°C
- Průběžně se adaptuje pomocí klouzavého průměru z posledních N cyklů

Systém automaticky ignoruje cykly přerušené okny, změnou teploty atd.

## 📊 Stavy systému

- **idle** - Teplota OK, TRV vypnutá
- **heating** - Aktivně topí, TRV zapnutá (35°C)
- **cooldown** - Po vypnutí měří překmit (20 min)
- **vent** - Okno otevřeno, TRV vypnutá
- **error** - Senzor/TRV offline, TRV vypnutá

Systém automaticky přepína mezi stavy podle teploty, stavu oken a dostupnosti zařízení.

## 📊 Diagnostické senzory

Pro každou místnost:

- **`sensor.trv_regulator_{room}_state`** - Aktuální stav (idle/heating/cooldown/vent/error)
- **`sensor.trv_regulator_{room}_learning`** - Stav učení a naučené parametry
- **`sensor.trv_regulator_{room}_last_cycle`** - Data z posledního topného cyklu  
- **`sensor.trv_regulator_{room}_history`** - Historie posledních 100 cyklů
- **`sensor.trv_regulator_{room}_stats`** - Statistiky (průměry, úspěšnost)
- **`sensor.trv_regulator_{room}_diagnostics`** - Stav komponent (diagnostic entity)
- **`sensor.trv_regulator_{room}_reliability`** - Spolehlivost komunikace s TRV

Pro celou integraci:
- **`sensor.trv_regulator_summary`** - Přehled všech místností

## 📊 Reliability Tracking

TRV Regulator automaticky sleduje spolehlivost komunikace s TRV hlavicemi a pomáhá identifikovat problémy se slabým Zigbee signálem.

### Sensory

#### Aggregate Reliability Sensor
`sensor.trv_regulator_{room}_reliability`

**State:** `weak` / `medium` / `strong` / `unknown`

**Atributy:**
- `reliability_rate`: % úspěšných příkazů (0-100)
- `signal_quality`: weak / medium / strong
- `failed_commands_24h`: Počet selhání za 24h
- `watchdog_corrections_24h`: Počet automatických oprav za 24h
- `signal_trend`: improving / stable / deteriorating
- `trv_statistics`: Per-TRV detaily pro každou hlavici:
  - `commands_sent`: Počet odeslaných příkazů
  - `commands_failed`: Počet selhání
  - `success_rate`: % úspěšnost (0-100)
  - `signal_quality`: weak / medium / strong
  - `preferred_mode`: Preferovaný hvac_mode (auto/heat)
  - `last_seen`: Čas posledního příkazu
- `command_history`: Historie posledních 10 příkazů (optimalizováno v3.0.18+)
- `correction_history`: Historie posledních 10 oprav (optimalizováno v3.0.18+)

**Poznámka:** `hourly_stats` a `daily_stats` byly odstraněny z atributů (zůstávají jen v JSON persistence)

### Signal Quality Thresholdy

- **Strong (≥98%)**: Vynikající signál, žádná akce potřeba
- **Medium (90-98%)**: Přijatelné, občasná selhání, zvážit přidání Zigbee routeru
- **Weak (<90%)**: Slabý signál, časté problémy - přidat Zigbee router!

### UI Vizualizace

Viz složka `examples/` pro ready-to-use Lovelace konfigurace:
- `lovelace_gauge.yaml` - Vizuální gauge indikátor
- `lovelace_complete.yaml` - Kompletní dashboard s detaily
- `lovelace_apexcharts.yaml` - Trend grafy (vyžaduje ApexCharts Card z HACS)

### Troubleshooting

**Slabý signál (weak):**
1. Zkontroluj `trv_statistics` - která konkrétní TRV má problém
2. Přidej Zigbee router poblíž problémové TRV
3. Sleduj `signal_trend` - měl by se změnit na "improving"

**Vysoký počet watchdog corrections:**
- Indikuje že TRV často zůstává v nesprávném stavu
- Obvykle způsobeno slabým Zigbee signálem
- Watchdog automaticky opravuje, ale měl bys zlepšit signál přidáním routeru

**Deteriorating trend:**
- Zkontroluj nové zdroje interference
- Ověř zdraví Zigbee sítě
- Zkontroluj baterie v TRV
- Zvaž přemístění Zigbee routerů

## ⚙️ Rychlost reakce

- **Teplota pokoje** - Okamžitá reakce při každé změně
- **Cílová teplota** - Debounce 15s (čeká na konec úpravy)
- **Okna** - Debounce 120s (ignoruje krátké větrání)
- **Periodický update** - Každých 30s (kontrola timerů)

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



## 🐛 Řešení problémů

**TRV se nespínají**
- Zkontroluj dostupnost entit v Developer Tools → States
- Ověř podporu `climate.set_hvac_mode` služby

**Systém v ERROR stavu**
- Zkontroluj teplotní senzor a TRV hlavice
- ERROR se vymaže automaticky když se zařízení vrátí

**Učení trvá dlouho**
- Sleduj `sensor.trv_regulator_{room}_learning` → `valid_cycles`
- Nevalidní cykly (okno, změna targetu) se nepočítají

**Velký překmit**
- V learning režimu normální (±1°C)
- Po naučení se automaticky adaptuje
- Zkus snížit `learning_cycles_required` na 5

**Další problémy?**
Otevři issue na [GitHubu](https://github.com/navratilpetr/trv_regulator/issues)



## 📄 Licence

MIT

## 👤 Autor

[@navratilpetr](https://github.com/navratilpetr)

## 🤝 Přispívání

Pull requesty jsou vítány! Pro větší změny nejdříve otevři issue pro diskuzi.

## ⭐ Podpora

Pokud se ti integrace líbí, dej hvězdičku na GitHubu!
