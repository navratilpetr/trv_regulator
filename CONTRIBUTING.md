# Contributing to TRV Regulator

Děkujeme za váš zájem přispět k TRV Regulator! 🎉

## Jak přispívat

### Hlášení chyb

Pokud jste našli chybu:
1. Zkontrolujte, zda již nebyla nahlášena v [Issues](https://github.com/navratilpetr/trv_regulator/issues)
2. Pokud ne, vytvořte nový issue s těmito informacemi:
   - Popis problému
   - Kroky k reprodukci
   - Očekávané chování
   - Skutečné chování
   - Verze Home Assistant a TRV Regulator
   - Relevantní logy

### Návrhy na vylepšení

Pro návrhy nových funkcí:
1. Vytvořte issue s popisem funkce
2. Popište použití a přínosy
3. Navrhněte možnou implementaci

### Pull Requesty

1. **Forkněte repozitář**
2. **Vytvořte novou branch**:
   ```bash
   git checkout -b feature/moje-funkce
   ```
3. **Nainstalujte vývojové závislosti**:
   ```bash
   pip install -r requirements-dev.txt
   ```
4. **Nastavte pre-commit hooks**:
   ```bash
   pre-commit install
   ```
5. **Proveďte změny** a dodržujte:
   - PEP 8 style guide
   - Type hints pro nové funkce
   - Docstrings pro nové třídy/funkce
   - Unit testy pro novou funkcionalitu

6. **Spusťte testy**:
   ```bash
   # Linting
   ruff check custom_components/
   black --check custom_components/
   mypy custom_components/trv_regulator/
   
   # Unit testy
   pytest tests/
   ```

7. **Commitujte změny**:
   ```bash
   git commit -m "feat: přidána nová funkce XYZ"
   ```
   
   Používejte [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` - nová funkcionalita
   - `fix:` - oprava chyby
   - `docs:` - dokumentace
   - `test:` - testy
   - `refactor:` - refaktoring
   - `chore:` - ostatní změny

8. **Pushněte do vaší fork**:
   ```bash
   git push origin feature/moje-funkce
   ```

9. **Vytvořte Pull Request** s popisem:
   - Co bylo změněno
   - Proč byla změna provedena
   - Jak bylo změněno testováno
   - Odkazy na související issues

## Vývojové prostředí

### Struktura projektu

```
trv_regulator/
├── custom_components/
│   └── trv_regulator/
│       ├── __init__.py          # Inicializace integrace
│       ├── config_flow.py       # UI konfigurace
│       ├── const.py             # Konstanty
│       ├── coordinator.py       # Data coordinator
│       ├── room_controller.py   # Hlavní logika
│       ├── sensor.py            # Senzory
│       ├── manifest.json        # Metadata
│       ├── services.yaml        # Definice služeb
│       └── strings.json         # Překlady
├── tests/                       # Unit testy
├── .github/workflows/           # GitHub Actions
├── requirements-dev.txt         # Vývojové závislosti
└── pyproject.toml              # Konfigurace nástrojů
```

### Lokální testování

Pro testování v Home Assistant:

1. **Zkopírujte do config Home Assistant**:
   ```bash
   cp -r custom_components/trv_regulator /path/to/homeassistant/config/custom_components/
   ```

2. **Restartujte Home Assistant**

3. **Sledujte logy**:
   ```bash
   tail -f /path/to/homeassistant/home-assistant.log | grep "TRV"
   ```

### Debugging

Povolte debug logging v `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.trv_regulator: debug
```

## Code Review Process

1. Maintainer zkontroluje kód
2. Může požádat o změny
3. Po schválení bude PR mergnut
4. Verze bude automaticky zvýšena podle labels:
   - `breaking` - major version
   - `feature` - minor version
   - ostatní - patch version

## Otázky?

Pokud máte dotazy, neváhejte otevřít issue nebo diskuzi na GitHubu.

Děkujeme za váš příspěvek! ❤️
