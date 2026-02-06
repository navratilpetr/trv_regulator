# Copilot Instructions for navratilpetr/trv_regulator

## 🔴 MANDATORY READING BEFORE EVERY PR

**ALWAYS read these files BEFORE creating a PR:**

1. **[PROMPT.md](../PROMPT.md)** - Complete integration specification
   - Architecture and state machine
   - What NOT to touch
   - Implementation rules

2. **[.github/COPILOT_CHANGELOG_RULES.md](COPILOT_CHANGELOG_RULES.md)** - CHANGELOG and versioning rules
   - How to update CHANGELOG.md
   - What you MUST NOT change (manifest.json)
   - Workflow behavior

---

## 🚫 CRITICAL RULES (NEVER VIOLATE)

### Version Management
❌ **NEVER change** `custom_components/trv_regulator/manifest.json` → version field
❌ **NEVER create** new version `## [X.Y.Z]` in CHANGELOG.md
✅ **ONLY add** to `## [Unreleased]` section in CHANGELOG.md

**Why?**
- Version bump happens AUTOMATICALLY via `bump-version.yaml` workflow
- If you change manifest.json, workflow will FAIL with "nothing to commit"
- Release won't be created automatically

### CI/CD
❌ **NEVER change** `.github/workflows/*` (unless user explicitly requests)

### Infrastructure
⚠️ Changes to `README.md`, `PROMPT.md` are OK
⚠️ But they do NOT require version bump

---

## ✅ WORKFLOW FOR EVERY PR

1. **READ PROMPT.md** - entire file
2. **READ COPILOT_CHANGELOG_RULES.md** - versioning rules
3. **Implement changes** according to specification
4. **Update CHANGELOG.md** - ONLY the `## [Unreleased]` section
5. **DO NOT add new version** - workflow does it automatically
6. **DO NOT touch manifest.json** - workflow changes it automatically

---

## 📋 Checklist before creating PR

- [ ] I have read PROMPT.md
- [ ] I have read COPILOT_CHANGELOG_RULES.md
- [ ] I did NOT add `## [X.Y.Z]` to CHANGELOG.md
- [ ] I did NOT change `version` in manifest.json
- [ ] I did NOT change `.github/workflows/*` (unless requested)
- [ ] Changes are consistent with PROMPT.md architecture

---

## 🔍 Validation

Every PR is automatically validated by `.github/workflows/validate-pr.yaml`:
- ❌ Rejects if manifest.json version was changed
- ❌ Rejects if new version section added to CHANGELOG.md
- ⚠️ Warns if workflow files were changed

**If validation fails:**
1. Read the error message
2. Revert the problematic changes
3. Follow the rules above
4. Push again
