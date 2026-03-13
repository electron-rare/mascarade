"""Agent Composants — Expert en sélection de composants électroniques et intégration JLCPCB."""

from mascarade.agents.base import Agent
from mascarade.router.router import Strategy


class ComponentsAgent(Agent):
    """Agent spécialisé pour la sélection de composants et l'optimisation pour JLCPCB."""

    def __init__(self):
        super().__init__(
            name="components-expert",
            description="Expert en sélection de composants électroniques — alternatives, datasheets, disponibilité, optimisation pour JLCPCB, génération de BOM et CPL.",
            system_prompt=(
                "You are an expert electronic components engineer with 20+ years of experience. "
                "Provide component selection guidance based on datasheets, availability, "
                "cost, and performance requirements. "
                "Specialized in JLCPCB component library optimization, LCSC part numbers, "
                "and manufacturing-ready BOM/CPL generation. "
                "Always consider: electrical parameters, thermal characteristics, "
                "supply chain availability, and PCB assembly constraints."
            ),
            preferred_provider="mistral",
            preferred_model="mistral-large-latest",
            strategy=Strategy.DOMAIN,
            tools=["jlcpcb_api", "lcsc_database", "python"],
            temperature=0.1,
            max_tokens=2048,
        )

    async def find_alternatives(self, component_spec: str, router) -> str:
        """Trouve des alternatives à un composant avec critères spécifiques."""
        prompt = (
            f"Find alternatives for this component:\n\n"
            f"{component_spec}\n\n"
            f"Provide:\n"
            f"1. Direct replacements (pin-compatible)\n"
            f"2. Functional equivalents\n"
            f"3. Cost/performance tradeoffs\n"
            f"4. Availability status (LCSC/JLCPCB part numbers)\n"
            f"5. Key selection criteria"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def optimize_for_jlcpcb(self, requirements: str, router) -> str:
        """Optimise la sélection de composants pour la fabrication JLCPCB."""
        prompt = (
            f"Optimize component selection for JLCPCB assembly:\n\n"
            f"{requirements}\n\n"
            f"Consider:\n"
            f"1. JLCPCB basic/extended parts library\n"
            f"2. LCSC part numbers and stock levels\n"
            f"3. PCB footprint compatibility\n"
            f"4. Cost optimization for assembly\n"
            f"5. Lead time and availability\n"
            f"6. Suggest specific LCSC part numbers"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def generate_bom(self, circuit_description: str, router) -> str:
        """Génère une BOM optimisée pour JLCPCB."""
        prompt = (
            f"Generate a JLCPCB-optimized BOM for:\n\n"
            f"{circuit_description}\n\n"
            f"BOM format:\n"
            f"Comment,Designator,Footprint,LCSC Part Number,Manufacturer,MPN,Quantity\n"
            f"Include:\n"
            f"1. JLCPCB-compatible components\n"
            f"2. LCSC part numbers where available\n"
            f"3. Footprint references\n"
            f"4. Quantity optimization\n"
            f"5. Cost estimates"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def generate_cpl(self, pcb_description: str, router) -> str:
        """Génère un fichier CPL (Component Placement List) pour JLCPCB."""
        prompt = (
            f"Generate CPL file for JLCPCB assembly:\n\n"
            f"{pcb_description}\n\n"
            f"CPL format:\n"
            f"Designator,Mid X,Mid Y,Rotation,Side\n"
            f"Consider:\n"
            f"1. Component placement order\n"
            f"2. Pick-and-place optimization\n"
            f"3. Top/bottom side designation\n"
            f"4. Rotation standards\n"
            f"5. Panelization requirements"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def check_availability(self, part_numbers: str, router) -> str:
        """Vérifie la disponibilité des composants chez JLCPCB/LCSC."""
        prompt = (
            f"Check availability for these components:\n\n"
            f"{part_numbers}\n\n"
            f"Provide:\n"
            f"1. Current stock levels\n"
            f"2. Lead times\n"
            f"3. Alternative suggestions if unavailable\n"
            f"4. MOQ (Minimum Order Quantity)\n"
            f"5. Pricing tiers"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def generate_gerber_notes(self, pcb_specs: str, router) -> str:
        """Génère des notes pour la fabrication Gerber chez JLCPCB."""
        prompt = (
            f"Generate fabrication notes for JLCPCB:\n\n"
            f"{pcb_specs}\n\n"
            f"Include:\n"
            f"1. Layer stackup requirements\n"
            f"2. Impedance control specifications\n"
            f"3. Solder mask/legend requirements\n"
            f"4. Via tenting instructions\n"
            f"5. Special manufacturing notes\n"
            f"6. JLCPCB capability references"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def select_jlcpcb_materials(self, requirements: str, router) -> str:
        """Sélectionne les matériaux optimaux pour la fabrication JLCPCB."""
        prompt = (
            f"Select optimal JLCPCB materials for:\n\n"
            f"{requirements}\n\n"
            f"Consider:\n"
            f"1. PCB thickness (0.4mm, 0.6mm, 0.8mm, 1.0mm, 1.2mm, 1.6mm, 2.0mm)\n"
            f"2. Base material (FR-4, FR-4 High Tg, Aluminum, Flexible)\n"
            f"3. Copper weight (0.5oz, 1oz, 2oz)\n"
            f"4. Solder mask color\n"
            f"5. Silkscreen color\n"
            f"6. Surface finish (HASL, ENIG, OSP)\n"
            f"7. Cost implications"
        )

        response = await self.run(prompt, router=router)
        return response.content


# Exemple d'utilisation
if __name__ == "__main__":
    # Cela nécessiterait un router configuré pour fonctionner
    agent = ComponentsAgent()
    print(f"Components Agent created: {agent.name}")
    print(f"Description: {agent.description}")
    print(f"System prompt: {agent.system_prompt[:100]}...")
