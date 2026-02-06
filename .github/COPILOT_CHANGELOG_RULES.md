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

---

## ⚠️ DŮLEŽITÉ: Workflow Detection

### Workflow detekce manuální změny

Workflow `bump-version.yaml` má **ochranný mechanismus** (řádky 88-95):

```yaml
- name: Check manual version change
  id: version_check
  run: |
    if git diff --name-only HEAD^ HEAD | grep -q "manifest.json"; then
      echo "⚠️ manifest.json changed in PR - using manual version"
      # POUŽIJE verzi z PR, ale má BUG!
    fi
```

**⚠️ POZOR: Tento mechanismus má BUG!**
- Detekuje že manifest.json byl změněn
- Pokusí se použít verzi z PR
- ALE pak selže s "nothing to commit" (soubory už jsou commitnuté)

**Proto STÁLE PLATÍ: NIKDY neměnit manifest.json!**

---

## 🛡️ Automatická ochrana

### Validation workflow

Každý PR je automaticky validován pomocí `.github/workflows/validate-pr.yaml`:

**Co kontroluje:**
- ✅ manifest.json nebyl změněn
- ✅ CHANGELOG.md nemá novou verzi (jen [Unreleased])
- ⚠️ Workflow soubory (warning pokud změněny)

**Pokud validation selže:**
- ❌ PR nemůže být mergnutý
- 📝 Detailní chybová zpráva s návodem na opravu
- 🔧 Musíš revertovat problematické změny

---

## 🐛 Known Issues

### Issue #1: Workflow fails with "nothing to commit"

**Kdy nastane:**
1. Copilot agent změní manifest.json v PR
2. PR se mergne
3. Workflow detekuje změnu
4. Pokusí se commitnout změny
5. ALE už tam jsou → FAIL: "nothing to commit, working tree clean"

**Proč to nastává:**
- Workflow má logiku pro "manual version bump"
- ALE táto logika má BUG
- Pokusí se commitnout soubory které už jsou v main

**Jak předejít:**
- ✅ NIKDY neměň manifest.json
- ✅ Validation workflow to automaticky zkontroluje
- ✅ PR selže pokud změníš manifest.json

**Jak opravit (pokud už nastalo):**

**A) Ruční vytvoření release (rychlé):**
```bash
git checkout main
git pull
git tag v3.0.X  # verze z manifest.json
git push origin v3.0.X

# Pak vytvoř release na GitHub UI:
# https://github.com/navratilpetr/trv_regulator/releases/new
# Tag: v3.0.X (vyber z existujících)
# Title: v3.0.X
# Description: (zkopíruj z CHANGELOG.md)
```

**B) Re-run workflow (pokud chceš dokončit přes workflow):**
```bash
# Lokálně revert manifest.json změny
git checkout main
git pull
git revert <commit-hash>  # commit který změnil manifest.json
git push origin main

# Pak re-run failed workflow na GitHub
```

---

## 🔍 Troubleshooting

### "Můj PR selhal na validate-pr workflow"

**1. Chyba: manifest.json was changed**

```bash
❌ ERROR: manifest.json was changed in this PR!
```

**Řešení:**
```bash
# Revert změny v manifest.json
git checkout main -- custom_components/trv_regulator/manifest.json
git commit -m "fix: revert manifest.json changes (handled by workflow)"
git push
```

---

**2. Chyba: New version section added to CHANGELOG.md**

```bash
❌ ERROR: New version section added to CHANGELOG.md!
```

**Řešení:**
Uprav CHANGELOG.md - odstraň řádek `## [X.Y.Z] - DATE`:

```markdown
# Špatně:
## [Unreleased]

## [3.0.25] - 2026-02-06  ← SMAŽ TENTO ŘÁDEK

### Přidáno
- Feature XYZ

# Správně:
## [Unreleased]

### Přidáno
- Feature XYZ
```

Pak commitni a pushni:
```bash
git add CHANGELOG.md
git commit -m "fix: update CHANGELOG format (workflow handles versioning)"
git push
```

---

## 📚 Související dokumentace

**Další zdroje:**
- [PROMPT.md](../PROMPT.md) - Kompletní pravidla pro Copilot agenty
  - Sekce "🚫 Co Copilot agent NESMÍ měnit"
- [.github/copilot-instructions.md](copilot-instructions.md) - Checklist pro každý PR
- [.github/workflows/validate-pr.yaml](workflows/validate-pr.yaml) - Automatická validace

