# CLI Agents — Rapport de Compatibilité Multi-Machines

> Date : 2026-03-21 | Tests effectués en conditions réelles

## Inventaire des Machines

| Machine | OS | Arch | Python | Node | GPU | Docker |
|---------|-----|------|--------|------|-----|--------|
| **grosmac** | macOS 25.3 | arm64 | 3.14.3 | 25.8.1 | Apple Silicon | - |
| **photon** | Photon OS 5 | x86_64 | 3.11.13 | 22.22.0 | - | 28.2.2 |
| **KXKM-AI** | Ubuntu | x86_64 | 3.12.3 | - | RTX 4090 | 29.3.0 |
| **Cils** | macOS 23.6 | x86_64 | 3.9.6 | - | - | - |
| **Tower** | Linux | x86_64 | 3.12.3 | 18.19.1 | - | - |

## Disponibilité des CLI Agents

| Machine | Vibe | Codex | Claude Code |
|---------|------|-------|-------------|
| **grosmac** | 2.5.0 | 0.116.0 | 2.1.81 |
| **photon** | 2.3.0 (fixé) | 0.115.0 | 2.1.76 |
| **KXKM-AI** | - | 0.114.0 (snap) | - |
| **Cils** | - | - | - |
| **Tower** | - | 0.107.0 | - |

## Tests Réels

### grosmac (Apple Silicon)

| Agent | Commande | Résultat | Latence |
|-------|----------|----------|---------|
| **Vibe** | `vibe --prompt "OK" --output json --max-turns 1` | **PASS** — Répond "OK" | ~3s |
| **Codex** | `codex exec --full-auto "OK"` | **QUOTA** — Fonctionne mais limite atteinte | ~5s |
| **Claude** | `claude --print --model haiku "OK"` | **PASS** — Répond "OK" | ~2s |

### photon (Serveur Production)

| Agent | Commande | Résultat | Action |
|-------|----------|----------|--------|
| **Vibe** | `vibe --prompt "OK" --output json` | **FIX NEEDED** — python3.12 n'était pas exécutable, chmod +x corrige | Fixé |
| **Codex** | `codex exec --full-auto "OK"` | **CONFIG** — Besoin de `--skip-git-repo-check` hors repo git | Fixé dans le code |
| **Claude** | `claude --print "OK"` | **AUTH** — API key invalide/absente | Configurer ANTHROPIC_API_KEY |

### KXKM-AI (GPU)

| Agent | Commande | Résultat | Action |
|-------|----------|----------|--------|
| **Vibe** | - | **NOT INSTALLED** | `curl -LsSf https://mistral.ai/vibe/install.sh \| bash` |
| **Codex** | `codex exec --full-auto "OK"` | **CONFIG** — `--skip-git-repo-check` nécessaire | Fixé |
| **Claude** | - | **NOT INSTALLED** | `npm install -g @anthropic-ai/claude-code` |

### Cils (macOS Intel)

| Agent | Résultat | Action |
|-------|----------|--------|
| **Vibe** | NOT INSTALLED | Python 3.9.6 trop ancien (besoin 3.12+) |
| **Codex** | NOT INSTALLED | Node.js absent |
| **Claude** | NOT INSTALLED | Node.js absent |

## Corrections Appliquées

1. **photon** : `chmod +x /root/.local/share/uv/python/cpython-3.12.12-linux-x86_64-gnu/bin/python3.12` — Vibe fonctionnel
2. **CodexAgent** : ajout `--skip-git-repo-check` pour fonctionner hors répertoire git
3. **CodexAgent** : `--quiet` → `--full-auto` (flag correct pour codex-cli 0.114+)

## Actions Restantes

| Machine | Action | Priorité |
|---------|--------|----------|
| **photon** | Configurer `ANTHROPIC_API_KEY` pour Claude Code | P1 |
| **photon** | Configurer `CODESTRAL_API_KEY` et `MISTRAL_API_KEY` dans .env | P1 |
| **KXKM-AI** | Installer Vibe (`curl -LsSf https://mistral.ai/vibe/install.sh \| bash`) | P2 |
| **KXKM-AI** | Installer Node.js + Claude Code | P2 |
| **Cils** | Mettre à jour Python 3.9 → 3.12+ (ou ignorer, machine secondaire) | P3 |
| **Tower** | Installer Vibe + Claude Code (Node 18 présent) | P2 |
