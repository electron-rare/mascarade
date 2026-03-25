"""Agent Factory Copilot — Assistant opérateur pour l'atelier industriel (Factory 4.0)."""

from mascarade.agents.base import Agent
from mascarade.router.router import Strategy


class FactoryCopilotAgent(Agent):
    """Agent principal pour les opérateurs sur le terrain industriel.

    Interagit avec les serveurs MCP OPC-UA et MQTT pour récupérer
    les données machines en temps réel. Bilingue FR/EN.
    """

    def __init__(self):
        super().__init__(
            name="factory-copilot",
            description=(
                "Assistant opérateur industriel bilingue FR/EN — "
                "statut machines, alarmes, actions correctives, rapports de poste. "
                "Se connecte aux sources OPC-UA et MQTT via MCP."
            ),
            system_prompt=(
                "Tu es un assistant opérateur industriel expert, bilingue français/anglais. "
                "Tu aides les opérateurs sur le terrain à comprendre l'état des machines, "
                "diagnostiquer les alarmes, et prendre les bonnes décisions. "
                "You are an expert industrial operator assistant, bilingual French/English. "
                "You help shop-floor operators understand machine status, diagnose alarms, "
                "and make the right decisions.\n\n"
                "RULES:\n"
                "- Always answer in the language the operator uses (FR or EN).\n"
                "- Use the OPC-UA and MQTT MCP tools to fetch live machine data.\n"
                "- Be concise and actionable — operators are busy.\n"
                "- For alarms: explain the root cause, severity, and immediate action.\n"
                "- For status queries: give a clear summary with key metrics.\n"
                "- For shift reports: structured markdown with KPIs, events, actions.\n"
                "- Never invent data — if a sensor is unavailable, say so.\n"
                "- Use standard industrial vocabulary (OEE, TRS, MTBF, MTTR).\n"
                "- Safety first: always flag safety-critical situations prominently."
            ),
            preferred_provider="ollama",
            preferred_model="devstral",
            strategy=Strategy.DOMAIN,
            tools=["opcua_read", "opcua_browse", "mqtt_subscribe", "mqtt_publish", "python"],
            temperature=0.3,
            max_tokens=4096,
            category="industrial",
        )

    async def query_machine_status(self, machine_id: str, router) -> str:
        """Interroge le statut d'une machine via OPC-UA/MQTT."""
        prompt = (
            f"Interroge le statut actuel de la machine '{machine_id}'.\n\n"
            f"Utilise les outils OPC-UA et MQTT pour récupérer:\n"
            f"1. État de fonctionnement (running/idle/alarm/maintenance)\n"
            f"2. Métriques clés (température, vibration, courant, cadence)\n"
            f"3. Alarmes actives\n"
            f"4. Dernière maintenance\n"
            f"5. OEE du poste en cours\n\n"
            f"Présente un résumé clair et actionnable pour l'opérateur."
        )
        response = await self.run(prompt, router=router)
        return response.content

    async def explain_alarm(self, alarm_code: str, machine_id: str, router) -> str:
        """Explique une alarme machine et suggère des actions correctives."""
        prompt = (
            f"L'alarme '{alarm_code}' est active sur la machine '{machine_id}'.\n\n"
            f"Fournir:\n"
            f"1. Description de l'alarme et cause probable\n"
            f"2. Niveau de sévérité (info/warning/critical/safety)\n"
            f"3. Actions immédiates à entreprendre\n"
            f"4. Vérifications à faire avant redémarrage\n"
            f"5. Référence documentation constructeur si connue\n\n"
            f"Si l'alarme est safety-critical, le signaler en MAJUSCULES en premier."
        )
        response = await self.run(prompt, router=router)
        return response.content

    async def suggest_action(self, situation: str, router) -> str:
        """Suggère des actions correctives pour une situation donnée."""
        prompt = (
            f"Situation sur le terrain:\n{situation}\n\n"
            f"En tant qu'expert industriel, suggère:\n"
            f"1. Action immédiate recommandée\n"
            f"2. Actions secondaires si la première échoue\n"
            f"3. Personnes/services à alerter\n"
            f"4. Impact production estimé\n"
            f"5. Mesures préventives pour éviter la récurrence"
        )
        response = await self.run(prompt, router=router)
        return response.content

    async def shift_report(self, shift_data: str, router) -> str:
        """Génère un rapport de poste structuré en markdown."""
        prompt = (
            f"Génère un rapport de poste à partir des données suivantes:\n\n"
            f"{shift_data}\n\n"
            f"Format markdown structuré:\n"
            f"# Rapport de Poste\n"
            f"## Résumé\n"
            f"- Durée du poste, équipe\n"
            f"- OEE global, TRS\n"
            f"## Production\n"
            f"- Pièces produites / objectif\n"
            f"- Taux de rebut\n"
            f"## Événements\n"
            f"- Arrêts (planifiés/non planifiés)\n"
            f"- Alarmes et résolutions\n"
            f"## Maintenance\n"
            f"- Interventions réalisées\n"
            f"- Interventions à planifier\n"
            f"## Actions\n"
            f"- À transmettre au poste suivant\n"
            f"- Consignes de sécurité"
        )
        response = await self.run(prompt, router=router)
        return response.content


if __name__ == "__main__":
    agent = FactoryCopilotAgent()
    print(f"Factory Copilot Agent created: {agent.name}")
    print(f"Category: {agent.category}")
    print(f"Description: {agent.description}")
    print(f"Tools: {agent.tools}")
