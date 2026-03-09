# Host Port Surface — 2026-03-08

Etat releve apres remediation `RA-003`.

## Ports Mascarade

| Port | Owner | Exposure cible | Justification |
| --- | --- | --- | --- |
| 80/tcp | `mascarade-edge-proxy` | `127.0.0.1` | reverse proxy local seulement tant qu'aucun besoin public explicite n'est valide |
| 443/tcp | `mascarade-edge-proxy` | `127.0.0.1` | meme politique que `80/tcp` |
| autres ports Docker Mascarade | stack `mascarade` | `127.0.0.1` | services d'admin, observability et backing services non destines au LAN par defaut |

## Ports host-level hors repo

| Port | Owner | Scope | Justification |
| --- | --- | --- | --- |
| 22/tcp | `sshd` systeme | public host-level | administration SSH de la machine, hors perimetre Docker `mascarade` |
| 3389/tcp | `gnome-remote-desktop-daemon` systeme | public host-level | acces bureau distant de la machine, hors perimetre Docker `mascarade` |

## Decision

- la stack `mascarade` ne publie plus `80/443` sur `0.0.0.0` par defaut;
- toute re-exposition LAN/public doit etre explicite via `.env`;
- les ports `22` et `3389` restent a traiter comme sujets host/VM, pas comme ports applicatifs `mascarade`.
