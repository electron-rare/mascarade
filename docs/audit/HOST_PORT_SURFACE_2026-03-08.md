# Host Port Surface — 2026-03-08

Etat releve apres remediation `RA-003`.

## Ports Mascarade

| Port | Owner | Exposure cible | Justification |
| --- | --- | --- | --- |
| 80/tcp | `mascarade-edge-proxy` | `0.0.0.0` | point d'entree public HTTP de la stack; sert `saillant.cc` et les hostnames operateur proxifies |
| 443/tcp | `mascarade-edge-proxy` | `0.0.0.0` | point d'entree public HTTPS; certificat Let's Encrypt wildcard installe via DNS-01 Cloudflare |
| autres ports Docker Mascarade | stack `mascarade` | `127.0.0.1` | services d'admin, observability et backing services non destines au LAN par defaut |

## Ports host-level hors repo

| Port | Owner | Scope | Justification |
| --- | --- | --- | --- |
| 22/tcp | `sshd` systeme | public host-level | administration SSH de la machine, hors perimetre Docker `mascarade` |
| 3389/tcp | `gnome-remote-desktop-daemon` systeme | public host-level | acces bureau distant de la machine, hors perimetre Docker `mascarade` |

## Decision

- la stack `mascarade` publie maintenant explicitement `80/443` sur `0.0.0.0` via `edge-proxy`;
- `Grafana`, `Langfuse` et `Dify` passent par des hostnames dedies derriere ce proxy;
- le proxy sert maintenant un certificat Let's Encrypt couvrant `saillant.cc` et `*.saillant.cc`;
- les ports `22` et `3389` restent a traiter comme sujets host/VM, pas comme ports applicatifs `mascarade`.
