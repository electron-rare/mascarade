# Historical Plan — Mascarade x Kill_LIFE Workflow Editor

Ce document conserve le plan d'origine qui a servi a lancer la lane `Kill_LIFE`
depuis `mascarade`.

Contrat courant a appliquer a la place de ce plan historique:

- `crazy_life` = repo canonique web/devops et release du shell cockpit
- `Kill_LIFE` = source de verite runtime, workflows JSON, evidence, firmware, CAD et compliance
- `mascarade` = repo compagnon runtime/ops + bridge historique optionnel

Consequence:

- les surfaces frontend/backend produit lancees initialement depuis `mascarade`
  doivent etre considerees comme des antecedents historiques ou des snapshots
  de bridge;
- la readiness de release du cockpit ne se decide plus dans `mascarade`;
- le bridge `mascarade/web` reste un mecanisme de sync, pas une source
  canonique.

Pour le contrat actif et la sequence de publication:

- `../crazy_life/docs/REPO_CARTOGRAPHY_2026-03-07.md`
- `../crazy_life/docs/PUBLISH_FLOW.md`
- `README.md`
