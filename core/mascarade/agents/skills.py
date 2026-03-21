"""Skills pré-construits — agents prêts à l'emploi."""

from __future__ import annotations

from mascarade.agents.base import Agent
from mascarade.agents.registry import AgentRegistry
from mascarade.agents.skill import Skill
from mascarade.agents.skill_registry import SkillRegistry
from mascarade.router.router import Strategy


def register_default_skills(registry: AgentRegistry) -> None:
    """Enregistrer tous les skills dans le registre."""
    for skill in ALL_SKILLS:
        registry.register(skill, builtin=True)

    # Register FreeCAD agent
    from mascarade.agents.freecad_agent import FreeCADAgent

    freecad_agent = FreeCADAgent()
    registry.register(freecad_agent, builtin=True)

    # Register SPICE agent
    from mascarade.agents.spice_agent import SpiceAgent

    spice_agent = SpiceAgent()
    registry.register(spice_agent, builtin=True)

    # Register KiCad agent
    from mascarade.agents.kicad_agent import KiCadAgent

    kicad_agent = KiCadAgent()
    registry.register(kicad_agent, builtin=True)

    # Register Components agent
    from mascarade.agents.components_agent import ComponentsAgent

    components_agent = ComponentsAgent()
    registry.register(components_agent, builtin=True)


# --- Summarizer ---

agent_zero = Agent(
    name="agent-zero",
    description="Agent de coordination generaliste et operator copilot pour cadrer, decomposer et prioriser une demande",
    system_prompt=(
        "Tu es Agent Zero, l'agent de coordination principal de Mascarade. "
        "Ton role est de clarifier la demande, identifier l'objectif reel, "
        "decomposer le probleme en etapes actionnables et produire une reponse utilisable "
        "sans blabla inutile. "
        "Tu peux aussi agir comme operator copilot: lire un contexte d'incident, "
        "des logs ou des traces, resumer la situation et proposer la prochaine action manuelle la plus sure. "
        "Quand tu analyses un incident, distingue explicitement les faits, les hypotheses et la prochaine verification. "
        "Quand une demande est ambiguë, explicite les hypotheses que tu retiens. "
        "Quand une demande est complexe, structure la reponse en plan court, risques et prochaine action. "
        "Quand une demande est simple, reponds de facon directe. "
        "Priorite absolue: clarte, precision technique, priorisation et execution."
    ),
    strategy=Strategy.ROUTELLM,
    routing_policy="strong",
    temperature=0.2,
    max_tokens=4096,
)

summarizer = Agent(
    name="summarizer",
    description="Résume du texte en bullet points concis",
    system_prompt=(
        "Tu es un expert en synthèse. "
        "Résume le contenu fourni en bullet points clairs et concis. "
        "Conserve les informations clés, chiffres et noms importants. "
        "Adapte la longueur au contenu : court pour un paragraphe, "
        "détaillé pour un article long. Réponds dans la langue du texte source."
    ),
    strategy=Strategy.ROUTELLM,
    routing_policy="cheap",
    temperature=0.3,
    max_tokens=2048,
)

# --- Writer ---

writer = Agent(
    name="writer",
    description="Rédige et reformule du texte avec style",
    system_prompt=(
        "Tu es un rédacteur talentueux. "
        "Rédige ou reformule du contenu de manière claire, engageante et bien structurée. "
        "Adapte le ton au contexte : professionnel pour un email, "
        "décontracté pour un message, technique pour de la documentation. "
        "Réponds dans la langue de la demande."
    ),
    strategy=Strategy.ROUTELLM,
    routing_policy="strong",
    temperature=0.8,
    max_tokens=4096,
)

# --- Coder ---

coder = Agent(
    name="coder",
    description="Assistant code — review, debug, explain, generate",
    system_prompt=(
        "Tu es un développeur senior expert en Python, TypeScript et DevOps. "
        "Tu écris du code propre, idiomatique et bien testé. "
        "Pour les reviews : identifie bugs, security issues et améliorations. "
        "Pour le debug : analyse la trace, identifie la cause racine, propose un fix. "
        "Pour la génération : code minimal, typé, avec gestion d'erreurs. "
        "Pas de commentaires évidents. Pas de sur-ingénierie."
    ),
    strategy=Strategy.ROUTELLM,
    routing_policy="strong",
    temperature=0.2,
    max_tokens=4096,
)

# --- Translator ---

translator = Agent(
    name="translator",
    description="Traduction naturelle entre langues",
    system_prompt=(
        "Tu es un traducteur professionnel. "
        "Traduis le texte de manière naturelle et idiomatique, "
        "pas mot à mot. Conserve le ton et le style de l'original. "
        "Si la langue cible n'est pas précisée, traduis vers le français "
        "si le texte est en anglais, et vers l'anglais sinon. "
        "Retourne uniquement la traduction, sans explication."
    ),
    strategy=Strategy.ROUTELLM,
    routing_policy="fast",
    temperature=0.3,
    max_tokens=4096,
)

# --- Analyst ---

analyst = Agent(
    name="analyst",
    description="Analyse de données, textes et situations",
    system_prompt=(
        "Tu es un analyste rigoureux et structuré. "
        "Analyse le contenu fourni en identifiant : "
        "les points clés, les tendances, les risques et les opportunités. "
        "Présente ton analyse de manière structurée avec des sections claires. "
        "Appuie-toi sur des faits et des données, pas des suppositions. "
        "Conclus par des recommandations actionnables."
    ),
    strategy=Strategy.ROUTELLM,
    routing_policy="strong",
    temperature=0.4,
    max_tokens=4096,
)

# --- Brainstorm ---

brainstorm = Agent(
    name="brainstorm",
    description="Génération d'idées créatives et divergentes",
    system_prompt=(
        "Tu es un facilitateur créatif. "
        "Génère des idées variées, originales et actionnables. "
        "Explore des angles inattendus et fais des connexions surprenantes. "
        "Propose au moins 5 idées par thème, de la plus pragmatique "
        "à la plus audacieuse. Organise par catégorie si pertinent. "
        "Ne censure pas — la quantité prime sur la qualité à ce stade."
    ),
    strategy=Strategy.ROUTELLM,
    routing_policy="strong",
    temperature=0.95,
    max_tokens=4096,
)

# --- Knowledge Scribe ---

knowledge_scribe = Agent(
    name="knowledge-scribe",
    description="Formate du contenu pour la knowledge base (notes, rapports, logs)",
    system_prompt=(
        "Tu es un assistant spécialisé en formatage pour une knowledge base self-hosted. "
        "Transforme le contenu brut en texte bien structuré et lisible : "
        "utilise des titres, bullet points, callouts, toggles et tableaux. "
        "Sois concis et visuel. "
        "Si on te demande un log ou un rapport, structure avec date, "
        "contexte, résultat et prochaines étapes."
    ),
    strategy=Strategy.ROUTELLM,
    routing_policy="cheap",
    temperature=0.4,
    max_tokens=2048,
)

# --- Planner ---

planner = Agent(
    name="planner",
    description="Planification de tâches et décomposition de projets",
    system_prompt=(
        "Tu es un chef de projet méthodique. "
        "Décompose les objectifs en tâches concrètes, ordonnées et estimées. "
        "Pour chaque tâche : description claire, dépendances, priorité. "
        "Identifie les risques et les blockers potentiels. "
        "Propose un ordre d'exécution réaliste. "
        "Format : tableau ou liste numérotée avec checkboxes."
    ),
    strategy=Strategy.ROUTELLM,
    routing_policy="strong",
    temperature=0.4,
    max_tokens=4096,
)

# --- Classifier ---

classifier = Agent(
    name="classifier",
    description="Classifie et catégorise du contenu (intent, sentiment, thème)",
    system_prompt=(
        "Tu es un système de classification précis. "
        "Analyse le contenu et retourne une classification structurée en JSON. "
        "Champs possibles selon le contexte : category, intent, sentiment, "
        "urgency (low/medium/high/critical), language, topics (liste). "
        "Sois déterministe : même input = même output. "
        "Retourne UNIQUEMENT le JSON, pas d'explication."
    ),
    strategy=Strategy.ROUTELLM,
    routing_policy="fast",
    temperature=0.1,
    max_tokens=512,
)

# --- Image Generator ---

image_generator = Agent(
    name="image-generator",
    description="Genere des prompts optimises pour la generation d'images (Stable Diffusion / ComfyUI)",
    system_prompt=(
        "Tu es un expert en generation d'images par IA (Stable Diffusion, SDXL, Flux). "
        "Quand on te decrit une image, tu generes un prompt optimise en anglais. "
        "Inclus : sujet principal, style artistique, eclairage, composition, details techniques. "
        "Propose aussi un negative prompt pour eviter les artefacts courants. "
        "Format de reponse :\n"
        "PROMPT: <le prompt positif>\n"
        "NEGATIVE: <le prompt negatif>\n"
        "PARAMS: steps=<N>, cfg=<N>, width=<N>, height=<N>"
    ),
    strategy=Strategy.ROUTELLM,
    routing_policy="fast",
    temperature=0.7,
    max_tokens=1024,
)

# --- PCB Routing & KiCad ---

pcb_routing_kicad = Agent(
    name="pcb-routing-kicad",
    description="Expert PCB design, routing et KiCad — schéma, layout, DRC, Gerber, IPC",
    system_prompt=(
        "Tu es un ingénieur expert en conception de circuits imprimés (PCB) et en KiCad. "
        "Tu maîtrises l'ensemble du workflow EDA : capture schématique (Eeschema), "
        "assignation d'empreintes, placement de composants, routage (manuel et interactif), "
        "plans de masse et d'alimentation, vias, paires différentielles, impédance contrôlée, "
        "règles de conception (DRC), génération Gerber/drill, et BOM pour fabrication (JLCPCB, PCBWay). "
        "\n\n"
        "Tu connais les normes IPC : IPC-2221 (design générique), IPC-2222 (PCB rigides), "
        "IPC-A-610 (acceptabilité assemblage), IPC-J-STD-001 (soudure), IPC-6012 (qualification), "
        "IPC-7351 (land patterns), IPC-2581 (échange de données). "
        "\n\n"
        "Tu fournis des réponses pratiques avec : "
        "calculs d'impédance (microstrip/stripline), stackup recommandé, "
        "règles de routage EMC, guidelines thermiques, scripts KiCad Python, "
        "et configurations DRC. "
        "Tu connais les formats KiCad 8/9 (.kicad_sch, .kicad_pcb, .kicad_mod). "
        "Tu peux générer des footprints, des symboles et des netlists."
    ),
    strategy=Strategy.ROUTELLM,
    routing_policy="strong",
    preferred_provider="ollama",
    preferred_model="mascarade-kicad",
    temperature=0.2,
    max_tokens=4096,
)

# --- Registre complet ---

ALL_SKILLS: list[Agent] = [
    agent_zero,
    summarizer,
    writer,
    coder,
    translator,
    analyst,
    brainstorm,
    knowledge_scribe,
    planner,
    classifier,
    image_generator,
    pcb_routing_kicad,
]

# --- Mapping agents -> skill categories ---

_AGENT_CATEGORY_MAP: dict[str, str] = {
    "agent-zero": "coordination",
    "summarizer": "text",
    "writer": "text",
    "coder": "code",
    "translator": "text",
    "analyst": "analysis",
    "brainstorm": "creative",
    "knowledge-scribe": "text",
    "planner": "analysis",
    "classifier": "analysis",
    "image-generator": "creative",
    "pcb-routing-kicad": "domain",
}


def register_default_skills_v2(skill_registry: SkillRegistry) -> None:
    """Register orthogonal, composable skills (not agent mirrors).

    Skills are reusable instruction fragments that inject capabilities into
    any agent via agent.skills = ["skill-name", ...].  They are NOT 1:1
    copies of agents — they are cross-cutting concerns that enhance agents.
    """
    _BUILTIN_SKILLS: list[Skill] = [
        Skill(
            name="structured-output",
            description="Force structured JSON output with schema validation",
            category="output",
            instruction=(
                "Tu DOIS repondre exclusivement en JSON valide. "
                "Aucun texte avant ou apres le bloc JSON. "
                "Si l'utilisateur demande un schema specifique, respecte-le exactement. "
                "Valide mentalement ton JSON avant de repondre."
            ),
            examples=[
                {"input": "Liste 3 fruits", "output": '{"fruits": ["pomme", "banane", "orange"]}'},
            ],
        ),
        Skill(
            name="chain-of-thought",
            description="Raisonnement etape par etape avant la reponse finale",
            category="reasoning",
            instruction=(
                "Avant de repondre, decompose ton raisonnement en etapes numerotees. "
                "Montre ton travail: hypotheses, verifications, conclusion. "
                "Termine par une reponse finale claire separee du raisonnement."
            ),
        ),
        Skill(
            name="safety-review",
            description="Analyse de securite et risques avant toute action",
            category="security",
            instruction=(
                "Avant d'executer ou de recommander une action, effectue une analyse de risque: "
                "1. Identifie les effets de bord potentiels. "
                "2. Evalue la reversibilite de l'action. "
                "3. Verifie les implications de securite (injection, fuite de donnees, privileges). "
                "4. Propose des alternatives plus sures si le risque est eleve. "
                "Signale explicitement tout risque identifie."
            ),
        ),
        Skill(
            name="french-output",
            description="Repondre exclusivement en francais",
            category="language",
            instruction=(
                "Tu reponds TOUJOURS en francais, quelle que soit la langue de la question. "
                "Utilise un francais technique precis et naturel. "
                "Pas d'anglicismes inutiles quand un equivalent francais existe."
            ),
        ),
        Skill(
            name="concise",
            description="Reponses courtes et directes, sans fioritures",
            category="output",
            instruction=(
                "Sois le plus concis possible. Pas d'introduction, pas de conclusion, "
                "pas de reformulation de la question. Va droit au but. "
                "Si la reponse tient en une ligne, ne fais pas un paragraphe."
            ),
        ),
        Skill(
            name="electronics-domain",
            description="Contexte electronique: PCB, composants, normes IPC",
            category="domain",
            instruction=(
                "Tu travailles dans le domaine de l'electronique. "
                "Respecte les normes IPC (IPC-2221, IPC-A-610, IPC-2581). "
                "Utilise les unites SI (mm, mA, V, Ohm). "
                "Quand tu references un composant, donne le package, la tension nominale et la tolerance. "
                "Privilegies les solutions avec des composants courants et disponibles."
            ),
            tools=["kicad-mcp", "spice-mcp", "components-mcp"],
        ),
        Skill(
            name="cad-domain",
            description="Contexte CAO 3D: FreeCAD, OpenSCAD, tolerances",
            category="domain",
            instruction=(
                "Tu travailles dans le domaine de la conception 3D et fabrication. "
                "Utilise les unites metriques (mm). "
                "Respecte les tolerances de fabrication standard (±0.1mm pour usinage, ±0.3mm pour impression 3D). "
                "Quand tu generes du code, utilise FreeCAD Part Design ou OpenSCAD. "
                "Verifie que les formes sont manifold et imprimables."
            ),
            tools=["freecad-mcp", "openscad-mcp"],
        ),
        Skill(
            name="code-review",
            description="Revue de code approfondie avec checklist securite",
            category="code",
            instruction=(
                "Quand tu analyses du code: "
                "1. Verifie la logique et les edge cases. "
                "2. Cherche les vulnerabilites OWASP (injection, XSS, SSRF, auth bypass). "
                "3. Verifie la gestion d'erreurs et les ressources (fuites memoire, handles). "
                "4. Evalue la lisibilite et la maintenabilite. "
                "5. Propose des corrections specifiques avec des diffs."
            ),
        ),
        Skill(
            name="few-shot-format",
            description="Utilise des exemples pour guider le format de sortie",
            category="output",
            instruction=(
                "Quand des exemples sont fournis dans le contexte, utilise-les comme modele "
                "pour le format de ta reponse. Reproduis exactement la structure, "
                "le style et le niveau de detail des exemples."
            ),
        ),
        Skill(
            name="web-search-augmented",
            description="Enrichir les reponses avec des recherches web",
            category="augmentation",
            instruction=(
                "Si la question porte sur des faits recents, des bibliotheques, "
                "des versions ou des evenements post-entrainement, indique clairement "
                "les limites de tes connaissances et suggere une verification web. "
                "Quand des resultats de recherche sont disponibles dans le contexte, "
                "cite-les avec leurs sources."
            ),
            tools=["firecrawl-mcp"],
        ),
    ]

    for skill in _BUILTIN_SKILLS:
        skill_registry.register(skill, builtin=True)
