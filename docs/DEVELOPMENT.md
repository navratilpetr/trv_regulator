# Development Guide

## Nastavení vývojového prostředí

### Požadavky

- Python 3.11 nebo novější
- Home Assistant (pro testování)
- Git

### Krok za krokem

1. **Fork a klonování**
   ```bash
   git clone https://github.com/YOUR_USERNAME/trv_regulator.git
   cd trv_regulator
   ```

2. **Vytvoření virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # nebo
   venv\Scripts\activate  # Windows
   ```

3. **Instalace závislostí**
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Nastavení pre-commit hooks**
   ```bash
   pre-commit install
   ```

## Struktura projektu

```
trv_regulator/
├── custom_components/trv_regulator/
│   ├── __init__.py              # Entry point, setup integrace
│   ├── config_flow.py           # UI konfigurace (Config Flow)
│   ├── const.py                 # Konstanty a výchozí hodnoty
│   ├── coordinator.py           # Data coordinator (komunikace se senzory)
│   ├── room_controller.py       # Hlavní logika - stavový automat
│   ├── sensor.py                # Diagnostické senzory
│   ├── manifest.json            # Metadata integrace
│   ├── services.yaml            # Definice služeb
│   └── strings.json             # Překlady UI texů
├── tests/                       # Unit testy
├── .github/                     # GitHub workflows, templates
└── docs/                        # Dokumentace
```

### Klíčové komponenty

#### RoomController (`room_controller.py`)
- Stavový automat pro řízení místnosti
- Řídí přechody mezi stavy: IDLE, HEATING, COOLDOWN, VENT, ERROR
- Implementuje učící algoritmus a prediktivní vypínání
- Spravuje historii cyklů a persistence

#### Coordinator (`coordinator.py`)
- DataUpdateCoordinator pro Home Assistant
- Periodicý update (30s)
- Zprostředkovává komunikaci mezi HA a RoomController

#### Config Flow (`config_flow.py`)
- Třístupňový průvodce konfigurací
- Options Flow pro změnu nastavení
- Validace vstupů

## Debugging

### Lokální testování v Home Assistant

1. **Zkopírujte do Home Assistant**
   ```bash
   cp -r custom_components/trv_regulator ~/.homeassistant/custom_components/
   ```

2. **Povolte debug logging**

   V `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.trv_regulator: debug
   ```

3. **Restartujte Home Assistant**
   ```bash
   ha core restart
   ```

4. **Sledujte logy**
   ```bash
   tail -f ~/.homeassistant/home-assistant.log | grep "TRV"
   ```

## Testování

### Unit testy

```bash
# Spustit všechny testy
pytest

# Spustit s coverage
pytest --cov=custom_components/trv_regulator --cov-report=html

# Spustit konkrétní test
pytest tests/test_const.py

# Spustit s verbose výstupem
pytest -v
```

### Code Quality

```bash
# Formátování kódu
black custom_components/

# Linting
ruff check custom_components/

# Type checking
mypy custom_components/trv_regulator/

# Spustit všechny checks (jako CI)
pre-commit run --all-files
```

## Přidání nové funkcionality

### Checklist

1. **Vytvořte branch**
   ```bash
   git checkout -b feature/moje-nova-funkce
   ```

2. **Implementujte změny**
   - Přidejte type hints
   - Napište docstrings
   - Dodržujte existující code style

3. **Přidejte testy**
   ```python
   # tests/test_nova_funkce.py
   def test_nova_funkce():
       assert nova_funkce() == expected_result
   ```

4. **Aktualizujte dokumentaci**
   - README.md (pokud je to user-facing funkce)
   - CHANGELOG.md (přidejte pod `[Unreleased]`)
   - Docstrings v kódu

5. **Spusťte testy a linting**
   ```bash
   pytest
   pre-commit run --all-files
   ```

6. **Commitujte změny**
   ```bash
   git add .
   git commit -m "feat: přidána nová funkce XYZ"
   ```

7. **Pushněte a vytvořte PR**
   ```bash
   git push origin feature/moje-nova-funkce
   ```

## Potřebujete pomoc?

- Otevřete [Issue](https://github.com/navratilpetr/trv_regulator/issues)
- Přečtěte si [CONTRIBUTING.md](../CONTRIBUTING.md)
