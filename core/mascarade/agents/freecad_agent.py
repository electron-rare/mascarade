"""Agent FreeCAD — spécialisé dans la conception 3D et l'ingénierie avec FreeCAD."""

from mascarade.agents.base import Agent
from mascarade.router.router import Strategy


class FreeCADAgent(Agent):
    """Agent spécialisé pour FreeCAD — conception paramétrique, modélisation 3D, et automatisation."""

    def __init__(self):
        super().__init__(
            name="freecad-designer",
            description="Agent expert en conception 3D avec FreeCAD — modélisation paramétrique, scripts Python, et bonnes pratiques de design.",
            system_prompt=(
                "You are an expert FreeCAD designer and engineer. "
                "You specialize in parametric 3D modeling, CAD automation, and mechanical design. "
                "Provide detailed, step-by-step guidance for FreeCAD workflows, "
                "Python scripting, and best practices for mechanical engineering projects. "
                "Always include practical examples and code snippets when relevant."
            ),
            preferred_provider="mistral",
            preferred_model="mistral-large-latest",
            strategy=Strategy.DOMAIN,
            tools=["python", "freecad_mcp"],
            temperature=0.3,
            max_tokens=2048,
        )

    async def generate_freecad_script(self, design_description: str, router) -> str:
        """Générer un script Python pour FreeCAD basé sur une description."""
        prompt = (
            f"Generate a complete FreeCAD Python script for the following design:\n\n"
            f"{design_description}\n\n"
            f"The script should include:\n"
            f"1. Document creation\n"
            f"2. Parametric dimensions\n"
            f"3. Step-by-step feature creation\n"
            f"4. Proper error handling\n"
            f"5. Comments explaining each step"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def explain_freecad_concept(self, concept: str, router) -> str:
        """Expliquer un concept FreeCAD avec des exemples pratiques."""
        prompt = (
            f"Explain the FreeCAD concept: {concept}\n\n"
            f"Provide:\n"
            f"1. Clear definition\n"
            f"2. Practical use cases\n"
            f"3. Step-by-step example\n"
            f"4. Common pitfalls and solutions\n"
            f"5. Related FreeCAD features/tools"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def debug_freecad_issue(self, problem_description: str, router) -> str:
        """Aider à déboguer un problème FreeCAD."""
        prompt = (
            f"Help debug this FreeCAD issue:\n\n"
            f"{problem_description}\n\n"
            f"Provide:\n"
            f"1. Possible causes\n"
            f"2. Step-by-step debugging approach\n"
            f"3. Python code to diagnose the issue\n"
            f"4. Common solutions\n"
            f"5. Prevention tips"
        )

        response = await self.run(prompt, router=router)
        return response.content


# Exemple d'utilisation
if __name__ == "__main__":
    # Cela nécessiterait un router configuré pour fonctionner
    agent = FreeCADAgent()
    print(f"FreeCAD Agent created: {agent.name}")
    print(f"Description: {agent.description}")
    print(f"System prompt: {agent.system_prompt[:100]}...")
