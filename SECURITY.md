# Security Policy

## Reporting a Vulnerability

Bezpečnost TRV Regulator bereme vážně. Pokud jste objevili bezpečnostní zranitelnost, prosím nahlaste ji zodpovědně.

### Jak nahlásit

**Nehlaste bezpečnostní zranitelnosti prostřednictvím veřejných GitHub issues.**

Místo toho použijte GitHub Security Advisory:
https://github.com/navratilpetr/trv_regulator/security/advisories/new

### Co zahrnout v reportu

- Typ zranitelnosti
- Postup pro reprodukci
- Potenciální dopad
- Návrhy na opravu (volitelné)

### Co očekávat

- **Potvrzení** vašeho reportu do 48 hodin
- **Pravidelné aktualizace** o průběhu řešení
- **Uznání** ve fix release notes (pokud si přejete)

## Bezpečnostní opatření v TRV Regulator

### Aktuální implementace

1. **Validace vstupů**: Všechny vstupy z UI jsou validovány
2. **Error handling**: Bezpečné vypnutí TRV při chybě
3. **Post-restart safety**: Automatický reset po restartu HA
4. **Timeouty**: Prevence nekonečného topení

### Známá omezení

- Integrace závisí na bezpečnosti Home Assistant
- Vyžaduje důvěryhodné senzory a TRV zařízení
- Ukládání do `.storage` (přístupná pouze HA)

### Best Practices pro uživatele

1. **Aktualizujte** na nejnovější verzi
2. **Používejte** důvěryhodné Zigbee/WiFi zařízení
3. **Kontrolujte** logy pro neobvyklé chování
4. **Nastavte** bezpečné limity (max_heating_duration)

## Bezpečnostní aktualizace

Bezpečnostní záplaty jsou vydávány co nejdříve a označeny jako:
- **Critical**: Okamžitá aktualizace doporučena
- **High**: Aktualizace doporučena do 7 dnů
- **Medium**: Aktualizace doporučena do 30 dnů

## Historie bezpečnostních záplat

Žádné známé bezpečnostní záplaty zatím nebyly vydány.

## Kontakt

Pro bezpečnostní dotazy: [GitHub Security](https://github.com/navratilpetr/trv_regulator/security)
