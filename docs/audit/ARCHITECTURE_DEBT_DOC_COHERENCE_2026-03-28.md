# Audit Dette Architecture/Doc — 2026-03-28

## Objectif

Suivre les ecarts de coherence entre code, runbooks et documentation active.

## Constats principaux

- Plusieurs documents historiques contiennent des chemins absolus machine.
- L'index documentaire et la gouvernance d'archive etaient absents ou incomplets.
- Des references operationnelles pointaient encore vers des worktrees externes.

## Correctifs engages

- Creation de [docs/index.md](docs/index.md)
- Creation de [docs/CONSOLIDATION_STATUS.md](docs/CONSOLIDATION_STATUS.md)
- Creation de [docs/archive/README.md](docs/archive/README.md)
- Remplacement de chemins absolus critiques dans les docs de pilotage

## Suite

- Etendre la normalisation des liens sur l'ensemble `docs/ + racine`.
- Consolider les doublons thematiques en gardant un document canonique par sujet.
