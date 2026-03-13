"""Agent KiCad — Expert en conception de circuits imprimés."""

from mascarade.agents.base import Agent
from mascarade.router.router import Strategy


class KiCadAgent(Agent):
    """Agent spécialisé pour KiCad — conception de schématiques, layout PCB, règles de design."""

    def __init__(self):
        super().__init__(
            name="kicad-designer",
            description="Expert KiCad — crée des schématiques optimisés, optimise les layouts PCB, applique les règles de design, génère les fichiers de fabrication et fournit les meilleures pratiques de conception.",
            system_prompt=(
                "You are an expert KiCad PCB designer with 15+ years of experience. "
                "Create optimized schematics and PCB layouts following industry standards. "
                "Apply design rules for manufacturability and signal integrity. "
                "Generate complete manufacturing files (Gerber, drill, BOM, pick-and-place). "
                "Provide detailed explanations and best practices for each design decision. "
                "Always follow KiCad conventions and include DRC checks."
            ),
            preferred_provider="mistral",
            preferred_model="mistral-large-latest",
            strategy=Strategy.DOMAIN,
            tools=["kicad_api", "python"],
            temperature=0.2,
            max_tokens=2048,
        )

    async def generate_schematic(self, requirements: str, router) -> str:
        """Génère un schéma KiCad à partir des exigences."""
        prompt = (
            f"Create a KiCad schematic for the following requirements:\n\n"
            f"{requirements}\n\n"
            f"Include:\n"
            f"1. Complete symbol placement\n"
            f"2. Proper net labeling\n"
            f"3. Power flags and ground symbols\n"
            f"4. Design rules and constraints\n"
            f"5. Brief explanation of design choices"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def optimize_layout(self, constraints: str, router) -> str:
        """Optimise le layout PCB selon les contraintes."""
        prompt = (
            f"Optimize this PCB layout with the following constraints:\n\n"
            f"{constraints}\n\n"
            f"Provide:\n"
            f"1. Component placement strategy\n"
            f"2. Routing optimization\n"
            f"3. Signal integrity considerations\n"
            f"4. Thermal management\n"
            f"5. Manufacturing recommendations"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def generate_footprint(self, component_description: str, router) -> str:
        """Génère un footprint KiCad pour un composant."""
        prompt = (
            f"Create a KiCad footprint for this component:\n\n"
            f"{component_description}\n\n"
            f"Include:\n"
            f"1. Pad layout and dimensions\n"
            f"2. Silkscreen markings\n"
            f"3. Courtyard definition\n"
            f"4. 3D model reference if available\n"
            f"5. Design rule checks"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def perform_drc(self, design_rules: str, router) -> str:
        """Effectue une vérification des règles de design."""
        prompt = (
            f"Perform Design Rule Check (DRC) with these rules:\n\n"
            f"{design_rules}\n\n"
            f"Check for:\n"
            f"1. Clearance violations\n"
            f"2. Trace width compliance\n"
            f"3. Via specifications\n"
            f"4. Silkscreen issues\n"
            f"5. Manufacturing constraints"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def generate_manufacturing_files(self, pcb_description: str, router) -> str:
        """Génère les fichiers de fabrication."""
        prompt = (
            f"Generate complete manufacturing files for this PCB:\n\n"
            f"{pcb_description}\n\n"
            f"Include:\n"
            f"1. Gerber files (F.Cu, B.Cu, F.SilkS, etc.)\n"
            f"2. Drill files\n"
            f"3. Bill of Materials (BOM)\n"
            f"4. Pick-and-place file\n"
            f"5. Assembly drawings"
        )

        response = await self.run(prompt, router=router)
        return response.content


# Exemple d'utilisation
if __name__ == "__main__":
    # Cela nécessiterait un router configuré pour fonctionner
    agent = KiCadAgent()
    print(f"KiCad Agent created: {agent.name}")
    print(f"Description: {agent.description}")
    print(f"System prompt: {agent.system_prompt[:100]}...")
