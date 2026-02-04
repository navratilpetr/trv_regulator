# 📝 CHANGELOG.md - Pravidla pro Copilot Agenty

## ✅ SPRÁVNÝ postup

Když vytvářím PR s novými features/fixes:

1. **Piš změny POD `## [Unreleased]`**
   ```markdown
   ## [Unreleased]
   
   ### Přidáno
   - Nová feature XYZ
   
   ### Opraveno
   - Bug ABC
   
   ## [3.0.17] - 2026-02-04
   ```

2. **NIKDY nevytvářej novou verzi `## [X.Y.Z] - DATE`**
   - GitHub Actions to udělá automaticky při merge!

3. **Použij správné kategorie:**
   - `### Přidáno` - nové features
   - `### Změněno` - změny existujících features
   - `### Opraveno` - bugfixy
   - `### Odstraněno` - deprecated/removed features
   - `### Technické změny` - interní změny

---

## ❌ ŠPATNÝ postup

**NIKDY NEDĚLEJ:**

```markdown
## [Unreleased]

## [3.0.18] - 2026-02-04  ← NIKDY TOTO!

### Přidáno
- Feature...
```

**PROČ?**
- GitHub Actions automaticky vytvoří verzi při merge
- Ručně vytvořená verze způsobí duplicitu
- `bump-version.yaml` selže nebo vytvoří zmatky

---

## 🔄 Workflow

1. **PR vytvořen:**
   ```markdown
   ## [Unreleased]
   
   ### Přidáno
   - Feature Z
   ```

2. **PR merged do main:**
   - GitHub Actions spustí `bump-version.yaml`
   - Automaticky změní na:
   ```markdown
   ## [Unreleased]
   
   ## [3.0.18] - 2026-02-04 14:30
   
   ### Přidáno
   - Feature Z
   ```

3. **Vytvořen tag a release:**
   - Tag: `v3.0.18`
   - Release notes: automaticky z CHANGELOG

---

## 📋 Checklist pro Copilot Agenty

Když upravuješ CHANGELOG.md:

- [ ] Píšu POD `## [Unreleased]`
- [ ] NETVOŘÍM nový header `## [X.Y.Z] - DATE`
- [ ] Používám správné kategorie (Přidáno/Změněno/Opraveno)
- [ ] Popisuji změny jasně a stručně
- [ ] Přidávám emoji pro lepší čitelnost (🐛 🎯 📊 ⚙️)
- [ ] Neměním existující verze (pod `## [X.Y.Z]`)

---

## 🔧 manifest.json

**NIKDY neměň `version` v manifest.json v PR!**

- GitHub Actions změní verzi automaticky
- Pokud ji změníš ručně, workflow selže (kontrola na řádku 27-33)

**Verze se mění JEN přes labels:**
- `breaking` → major bump (3.0.0 → 4.0.0)
- `feature` → minor bump (3.0.0 → 3.1.0)
- žádný label → patch bump (3.0.0 → 3.0.1)
