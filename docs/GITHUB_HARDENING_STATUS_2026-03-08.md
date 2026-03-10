# GitHub Hardening Status — 2026-03-08

Perimetre verifie:

- `electron-rare/Kill_LIFE`
- `electron-rare/crazy_life`
- `electron-rare/mascarade`
- `electron-rare/agent-factory-cockpit`

## Etat courant

### CI

- `Kill_LIFE`: workflows presents (`ci`, `static`, `secret_scan`, `supply_chain`, etc.)
- `crazy_life`: workflow `ci.yml` present
- `mascarade`: workflow `ci.yml` present
- `agent-factory-cockpit`: workflow `ci.yml` ajoute pour bootstrap/lint/smoke

### Branch protection

- `Kill_LIFE`: protection `main` appliquee
- `crazy_life`: tentative refusee par GitHub
- `mascarade`: tentative refusee par GitHub
- `agent-factory-cockpit`: tentative refusee par GitHub

Erreur renvoyee par GitHub sur les repos prives bloques:

```text
Upgrade to GitHub Pro or make this repository public to enable this feature. (HTTP 403)
```

## Conclusion operative

Ce qui est effectivement en place aujourd hui:

- CI minimale sur les 4 repos
- repo prive `agent-factory-cockpit` cree et pousse sur `main`
- protection de `main` active sur `Kill_LIFE`

Ce qui reste bloque par le plan GitHub courant:

- protection native de `main` sur les repos prives `crazy_life`, `mascarade`, `agent-factory-cockpit`

## Recommandation

Tant que la limitation GitHub reste active:

- garder la discipline `PR only` en pratique, meme sans enforcement serveur
- utiliser les workflows CI comme garde-fou minimum avant push
- basculer les repos concernes sur un plan GitHub compatible, ou les rendre publics, si la protection native de branche doit devenir obligatoire
