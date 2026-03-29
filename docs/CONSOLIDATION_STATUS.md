# Consolidation Documentation

## Etat

- Scope: `docs/` + markdown racine
- Strategie: refactor complet avec archivage (sans suppression destructive)
- Langue canonique: francais

## Avancement

- [x] Creer un index canonique [docs/index.md](docs/index.md)
- [x] Creer un espace d'archive [docs/archive/README.md](docs/archive/README.md)
- [x] Corriger une premiere vague de chemins absolus critiques
- [x] Qualifier les reliquats historiques restants (2 rapports d'audit annotes)
- [ ] Etendre le nettoyage de liens au reste des docs historiques
- [ ] Lancer la consolidation thematique (E2E, P2P, deploiement, fine-tuning, KiCad)

## Notes d'implementation

- Les chemins absolus de machine locale (`/home/...`, `/Users/...`) ne doivent rester que dans des logs historiques explicitement marques.
- Toute nouvelle doc operationnelle doit etre portable depuis la racine du repo.
