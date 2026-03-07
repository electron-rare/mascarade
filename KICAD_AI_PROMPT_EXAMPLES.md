# 💬 KiCad AI Prompt Examples — Library

**Collection de prompts optimisés pour KiCad + MCP Server / KiC-AI**
**Version**: 1.0 | **Date**: 2026-03-06

---

## 📋 Structure des Prompts

Chaque exemple suit ce format:
```markdown
### 📌 [Catégorie] - [Description]
**Type**: MCP / KiC-AI / Hybride
**Complexité**: ⭐ to ⭐⭐⭐⭐⭐
**Modèle Recommandé**: llama3.2:3b / mistral:7b

**Prompt**:
```text
[Texte du prompt]
```

**Contexte Supplémentaire**:
- [Information utile]
- [Référence ou lien]

**Variantes**:
- [Variante 1]
- [Variante 2]
```

---

## 🔧 Création de Projet

### 📌 Nouveau Projet - Simple
**Type**: MCP
**Complexité**: ⭐
**Modèle**: llama3.2:3b

**Prompt**:
```text
Crée un nouveau projet KiCad nommé "STM32-DevBoard" avec les paramètres suivants:
- Emplacement: ~/projects/stm32-devboard
- Schéma principal: stm32-devboard.kicad_sch
- PCB: stm32-devboard.kicad_pcb
- Ajoute une page de titre avec le nom du projet et la date
```

**Contexte**:
- Utilise `create_project` via MCP
- Spécifiez toujours l'emplacement complet

**Variantes**:
- Ajoute un template spécifique: "...en utilisant le template 'arduino-shield'"
- Multi-sheets: "...avec 3 feuilles: main, power, connectors"

---

### 📌 Nouveau Projet - Avancé
**Type**: MCP
**Complexité**: ⭐⭐⭐
**Modèle**: mistral:7b

**Prompt**:
```text
Crée un projet pour un module LoRa avec ces spécifications:
1. Nom: "LoRa-Gateway-v2"
2. Emplacement: ~/projects/lora-gateway
3. Schéma avec 4 feuilles:
   - main: Circuit principal avec SX1276
   - power: Régulation 3.3V/5V
   - rf: Section RF avec filtres
   - connectors: Connecteurs SMA et UART
4. Ajoute ces champs globaux:
   - Company: Acme Corp
   - Engineer: [Votre Nom]
   - Revision: 1.0
   - Date: auto
5. Utilise le template "rf-design" pour la feuille RF
```

**Contexte**:
- Les feuilles hiérarchiques améliorent l'organisation
- Les champs globaux sont hérités par toutes les feuilles

---

## 📁 Gestion des Composants

### 📌 Ajouter Composant - Basique
**Type**: MCP
**Complexité**: ⭐
**Modèle**: llama3.2:3b

**Prompt**:
```text
Ajoute un microcontrôleur STM32F401CCU6 à la feuille principale avec:
- Position: (100, 100)
- Orientation: Horizontal
- Valeur: STM32F401CCU6
- Footprint: LQFP-48_7x7mm_P0.5mm
- Datasheet: https://www.st.com/resource/en/datasheet/stm32f401cc.pdf
```

**Contexte**:
- `add_schematic_component` via MCP
- Toujours spécifier position (x,y) en mm

---

### 📌 Ajouter Composant - Avec Règles
**Type**: Hybride (MCP + KiC-AI)
**Complexité**: ⭐⭐⭐
**Modèle**: mistral:7b

**Prompt**:
```text
Ajoute un régulateur buck TPS54360 avec:
1. Position: (150, 80)
2. Valeur: TPS54360DDAR
3. Footprint: SOT-23-6
4. Règles de design:
   - Trace width: 0.3mm pour VIN
   - Trace width: 0.6mm pour VOUT
   - Via stitching: 1 via/10mm pour les plans de masse
5. Ajoute ces composants passifs associés:
   - C1: 10µF/25V X5R 0603 (découplage entrée)
   - C2: 22µF/16V X5R 0805 (découplage sortie)
   - L1: 4.7µH 1A (inductance)
   - R1: 10kΩ 0603 (résistance de feedback)
```

**Contexte**:
- KiC-AI peut suggérer les composants passifs
- MCP les place automatiquement

---

### 📌 Recherche de Composant
**Type**: KiC-AI
**Complexité**: ⭐⭐
**Modèle**: llama3.2:3b

**Prompt**:
```text
Trouve un MOSFET N-channel avec ces spécifications:
- Tension Vds: ≥30V
- Courant Id: ≥5A
- Rds(on): <20mΩ
- Boîtier: SOT-23 ou DFN
- Disponible chez JLCPCB (LCSC)
- Prix < $0.50 pour qté 100

Liste les 3 meilleures options avec:
1. LCSC Part #
2. Fabricant/Part Number
3. Prix unitaire
4. Lien datasheet
```

**Contexte**:
- KiC-AI utilise Nexar API pour le pricing
- Toujours spécifier la quantité pour le pricing

---

## ✨ Routage et Layout

### 📌 Routage Automatique - Simple
**Type**: MCP
**Complexité**: ⭐⭐
**Modèle**: llama3.2:3b

**Prompt**:
```text
Route ces nets sur la couche supérieure avec:
- Net "VCC_3V3": largeur 0.8mm, priorité haute
- Net "GND": largeur 1.0mm, via stitching tous les 15mm
- Net "SDA": largeur 0.2mm, différentiel avec SCL
- Net "SCL": largeur 0.2mm, différentiel avec SDA

Règles:
- Espacement minimum: 0.2mm
- Via size: 0.3mm/0.6mm
- Évite les zones sous les composants BGA
```

**Contexte**:
- `route_pcb` via MCP
- Spécifiez toujours les largeurs en mm

---

### 📌 Optimisation de Layout
**Type**: KiC-AI
**Complexité**: ⭐⭐⭐
**Modèle**: mistral:7b

**Prompt**:
```text
Analyse ce layout PCB et recommande des optimisations pour:
1. Réduire les émissions EMI/EMC
2. Améliorer l'intégrité du signal pour les traces haute vitesse
3. Optimiser le placement thermique pour les composants chauds
4. Minimiser la longueur des traces critiques

Fournis des suggestions spécifiques avec:
- Changements proposés
- Justification technique
- Impact estimé
- Exemple de code MCP pour appliquer les changements
```

**Contexte**:
- Mode "Advisory" de KiC-AI
- Fournit des raisons techniques pour chaque recommandation

---

## 💰 Gestion BOM et Coûts

### 📌 Génération BOM - Basique
**Type**: KiC-AI
**Complexité**: ⭐
**Modèle**: llama3.2:3b

**Prompt**:
```text
Génère une liste de matériaux (BOM) pour ce projet avec:
- Format: CSV
- Champs: RefDes, Value, Footprint, Quantity, LCSC Part #, Manufacturer, MPN
- Trie par: RefDes
- Filtre: Exclure les composants DNP
```

**Contexte**:
- Utilise les champs LCSC pour JLCPCB
- Format CSV pour import facile

---

### 📌 Optimisation Coût
**Type**: KiC-AI
**Complexité**: ⭐⭐⭐
**Modèle**: mistral:7b

**Prompt**:
```text
Analyse la BOM actuelle et recommande des alternatives moins chères pour:
- U1 (ESP32-WROOM-32): cible <$4.50 @100pcs
- C1-C10 (100nF 0603): cible <$0.01 @1000pcs
- R1-R20 (10kΩ 0603): cible <$0.005 @5000pcs

Pour chaque composant, liste:
1. Option actuelle (prix, distributeur)
2. 3 alternatives avec prix/quantité
3. Impact sur les performances
4. Numéro LCSC pour JLCPCB

Priorise les composants en stock chez JLCPCB avec livraison rapide.
```

**Contexte**:
- Utilise Nexar API pour pricing réel
- Toujours vérifier l'impact technique

---

## 🔍 Analyse et Debugging

### 📌 Vérification DRC
**Type**: KiC-AI
**Complexité**: ⭐⭐
**Modèle**: llama3.2:3b

**Prompt**:
```text
Exécute une vérification DRC complète sur ce PCB et rapporte:
1. Erreurs critiques (court-circuits, nets non connectés)
2. Avertissements (espacement, largeurs de trace)
3. Problèmes de fabrication (trous trop petits, silk trop proche des pads)

Pour chaque problème, suggère:
- Description claire
- Emplacement (X,Y si possible)
- Solution recommandée
- Commandes MCP pour corriger
```

**Contexte**:
- Mode "Analysis" de KiC-AI
- Peut générer un rapport structuré

---

### 📌 Analyse EMI/EMC
**Type**: KiC-AI
**Complexité**: ⭐⭐⭐⭐
**Modèle**: mistral:7b

**Prompt**:
```text
Analyse ce design pour les problèmes EMI/EMC potentiels, en particulier:
1. Boucles de masse
2. Traces d'horloge non blindées
3. Plans de masse discontinus
4. Composants sensibles près des sources de bruit

Fournis un rapport détaillé avec:
- Description du problème
- Localisation sur le PCB
- Sévérité (Haute/Moyenne/Basse)
- Solution recommandée avec justification technique
- Référence aux normes (CISPR 22, FCC Part 15)
- Estimation de l'amélioration attendue

Inclut des suggestions pour:
- Blindage
- Filtrage
- Routage des traces critiques
- Découplage
```

**Contexte**:
- Nécessite une compréhension approfondie des principes EMI
- Le modèle doit avoir accès aux normes pertinentes

---

## 📦 Fabrication et Export

### 📌 Génération Gerber
**Type**: MCP
**Complexité**: ⭐⭐
**Modèle**: llama3.2:3b

**Prompt**:
```text
Exporte les fichiers Gerber pour fabrication chez JLCPCB avec:
- Format: RS-274X
- Couches: F.Cu, B.Cu, F.SilkS, B.SilkS, F.Mask, B.Mask, Edge.Cuts
- Précision: 4.6
- Unités: millimètres
- Inclure les couches User.1 et User.2 pour les découpes
- Génère un fichier ZIP nommé: ${TITLE}_${REVISION}_gerbers.zip
```

**Contexte**:
- `export_gerbers` via MCP
- Toujours inclure Edge.Cuts pour le contour

---

### 📌 Préparation JLCPCB
**Type**: Hybride
**Complexité**: ⭐⭐⭐
**Modèle**: mistral:7b

**Prompt**:
```text
Prépare ce projet pour fabrication chez JLCPCB:
1. Vérifie que tous les composants ont un numéro LCSC valide
2. Génère les fichiers requis:
   - Gerbers (RS-274X)
   - BOM (CSV avec LCSC Part #)
   - CPL (Pick & Place)
   - IPC netlist
3. Crée une archive ZIP nommée: ESP32-IoT_v1.2_production.zip
4. Vérifie:
   - Pas de DRC errors
   - Tous les nets connectés
   - Largeurs de trace ≥0.15mm
   - Espacement ≥0.15mm
   - Trous ≥0.3mm

Si des problèmes sont trouvés, liste-les avec des solutions.
```

**Contexte**:
- Utilise Fabrication Toolkit pour la génération
- MCP pour la vérification finale

---

## 🤖 Prompts Hybrides (MCP + KiC-AI)

### 📌 Design Complet - ESP32 IoT
**Type**: Hybride
**Complexité**: ⭐⭐⭐⭐
**Modèle**: mistral:7b

**Prompt**:
```text
Conçois un module IoT ESP32 avec ces étapes:

Étape 1 (MCP):
- Crée un projet "ESP32-IoT-v1"
- Ajoute ESP32-WROOM-32 à (100,100)
- Ajoute régulateur AMS1117-3.3 à (80,80)
- Ajoute connecteur USB-C à (150,50)

Étape 2 (KiC-AI - Analysis):
- Vérifie que le schéma suit les bonnes pratiques
- Recommande des valeurs pour les composants passifs
- Vérifie l'intégrité du signal pour les traces USB

Étape 3 (MCP):
- Route les pistes d'alimentation (VCC/GND) avec 20mil
- Route les signaux USB avec différentiel 5mil/5mil
- Ajoute des vias de stitching pour les plans de masse

Étape 4 (KiC-AI - Advisory):
- Optimise le placement pour la fabrication
- Vérifie les règles DRC
- Estime le coût pour 100 unités

Étape 5 (Fabrication Toolkit):
- Génère les fichiers pour JLCPCB
- Crée l'archive de production

Étape 6 (MCP):
- Compresse tous les fichiers
- Prépare pour livraison
```

**Contexte**:
- Combine les forces de MCP (automatisation) et KiC-AI (analyse)
- Workflow idéal pour les projets complexes

---

## 💡 Best Practices pour les Prompts

### 1. Spécificité
✅ **Bonne pratique**:
```text
"Ajoute un condensateur 100nF 0603 X7R avec LCSC C123456 à (50,50)"
```

❌ **À éviter**:
```text
"Ajoute un condensateur quelque part"
```

### 2. Contexte
Fournissez toujours:
- **Position**: Coordonnées (x,y)
- **Valeurs**: Tension, courant, tolérance
- **Références**: LCSC#, MPN, datasheet
- **Règles**: Largeurs, espacement, couches

### 3. Formatage
Utilisez des listes numérotées pour les étapes multiples:
```text
1. Faire A
2. Puis B
3. Enfin C
```

### 4. Validation
Demandez toujours une vérification:
```text
"Vérifie que X est correct et liste les erreurs"
```

### 5. Alternatives
Demandez des options:
```text
"Liste 3 alternatives pour ce composant avec prix"
```

---

## 📚 Références

### Documentation
- [KiCad MCP Server](https://github.com/mixelpixx/KiCAD-MCP-Server)
- [KiC-AI](https://github.com/jochemkroon/KiC-AI)
- [Fabrication Toolkit](https://github.com/bennymeg/Fabrication-Toolkit)

### Prompt Engineering
- [Anthropic Prompt Guide](https://docs.anthropic.com/claude/prompt-engineering)
- [KiCad Scripting Docs](https://docs.kicad.org/9.0/en/scripting/scripting.html)

---

*Library générée par Mistral Vibe 🤖 | 2026-03-06*
*Optimisé pour KiCad 9.0+ avec MCP Server et KiC-AI*
