# Industrial proxy groups 2026-03-14

## Decision

Le proxy industriel ne forwarde plus de groupes etendus par defaut.

Valeur par defaut:

- `EDGE_PROXY_INDUSTRIAL_GROUPS=operator`

Toute elevation (`approver`, `auditor`, `admin`) doit etre explicite via la variable d'environnement.

## Surfaces concernees

- `api/src/routes/ops.ts`
- `api/src/routes/mcpIndustrial.ts`
- surfaces `industrial.saillant.cc` exposees derriere `edge-proxy`

## Intent

- reduire le privilege par defaut sur la lane industrielle
- eviter qu'une doc ops ancienne laisse croire qu'un fallback implicite plus large existe encore
- garder un override simple si une exploitation locale legitime exige plus que `operator`

## Contract

- pas de fallback implicite vers `operator,approver,auditor,admin`
- pas de reintroduction de groupes par defaut dans le code
- toute extension passe par configuration explicite et revue operateur

## Validation

- validation runtime differee
- la source de verite immediate reste le code et cette note, pas les anciens artefacts d'audit
