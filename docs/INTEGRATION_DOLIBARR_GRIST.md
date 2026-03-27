# Integration Dolibarr + Grist

## Dolibarr (ERP/CRM)

Remplace Frappe pour la gestion commerciale.

### API REST

```
Base URL: DOLIBARR_URL (ex: https://erp.saillant.cc)
Auth: Header DOLAPIKEY: <token>
```

| Endpoint | Methode | Description |
|----------|---------|-------------|
| `/api/index.php/proposals` | GET | Lister les devis |
| `/api/index.php/proposals` | POST | Creer un devis |
| `/api/index.php/proposals/{id}` | PUT | Modifier un devis |
| `/api/index.php/invoices` | GET | Lister les factures |
| `/api/index.php/invoices` | POST | Creer une facture |
| `/api/index.php/thirdparties` | GET | Lister les contacts |
| `/api/index.php/tasks` | GET | Lister les taches |

### Agent mascarade

- **dolibarr-assistant** : Expert ERP/CRM, devis, factures, contacts
- MCP Server : `dolibarr_server.py` (6 tools)

### er-ops

- Toggle Frappe / Dolibarr dans Devis + Factures
- API module : `src/lib/dolibarr.ts`

## Grist (Base de donnees no-code)

Fait partie de La Suite Numerique. Remplace les tableurs.

### API REST

```
Base URL: GRIST_URL (ex: https://grist.saillant.cc)
Auth: Bearer token
```

| Endpoint | Methode | Description |
|----------|---------|-------------|
| `/api/docs` | GET | Lister les documents |
| `/api/docs/{id}/tables` | GET | Lister les tables |
| `/api/docs/{id}/tables/{t}/records` | GET | Lister les enregistrements |
| `/api/docs/{id}/tables/{t}/records` | POST | Ajouter un enregistrement |
| `/api/docs/{id}/tables/{t}/records` | PATCH | Modifier un enregistrement |

### Agent mascarade

- **grist-data** : Expert base de donnees, formules, analyse
- MCP Server : `grist_server.py` (4 tools)

### er-ops

- API module : `src/lib/grist.ts`

## Variables d'environnement

```env
# Dolibarr
DOLIBARR_URL=https://erp.saillant.cc
DOLIBARR_API_KEY=<token>

# Grist
GRIST_URL=https://grist.saillant.cc
GRIST_API_KEY=<token>

# er-ops
VITE_DOLIBARR_URL=https://erp.saillant.cc
VITE_DOLIBARR_TOKEN=<token>
VITE_GRIST_URL=https://grist.saillant.cc
VITE_GRIST_TOKEN=<token>
```
