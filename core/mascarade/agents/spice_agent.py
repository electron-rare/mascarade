"""Agent SPICE — Expert en simulation de circuits électroniques."""

from mascarade.agents.base import Agent


class SpiceAgent(Agent):
    """Agent spécialisé pour la simulation SPICE — génération de netlists, analyse de circuits, débogage."""

    def __init__(self):
        super().__init__(
            name="spice-expert",
            description="Expert en simulation SPICE — génère des netlists, effectue des analyses AC/DC/transitoires, débogue les problèmes de convergence et explique le comportement des circuits.",
            system_prompt=(
                "You are an expert SPICE simulation engineer with 20+ years of experience. "
                "Generate accurate, simulatable SPICE netlists for ngspice/LTspice. "
                "Perform AC, DC, and transient analysis with proper .control directives. "
                "Debug convergence issues systematically. Explain circuit behavior clearly. "
                "Always provide complete, ready-to-simulate code with proper device models."
            ),
            preferred_provider="mistral",
            preferred_model="mistral-large-latest",
            tools=["python", "spice_simulator"],
            temperature=0.1,
            max_tokens=3072,
        )

    async def generate_netlist(self, circuit_description: str, router) -> str:
        """Génère un netlist SPICE complet à partir d'une description de circuit."""
        prompt = (
            f"Generate a complete SPICE netlist for the following circuit:\n\n"
            f"{circuit_description}\n\n"
            f"Requirements:\n"
            f"1. Use appropriate device models with all required parameters\n"
            f"2. Include proper analysis directives (.op, .ac, .tran)\n"
            f"3. Add .control section with measurements if applicable\n"
            f"4. Ensure the netlist is ready for ngspice/LTspice\n"
            f"5. Provide a brief explanation of the circuit behavior"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def debug_convergence(self, error_message: str, netlist: str, router) -> str:
        """Débogue les problèmes de convergence SPICE."""
        prompt = (
            f"Debug this SPICE convergence issue:\n\n"
            f"Error message: {error_message}\n\n"
            f"Problematic netlist:\n{netlist}\n\n"
            f"Provide:\n"
            f"1. Root cause analysis\n"
            f"2. Step-by-step solution\n"
            f"3. Modified netlist with fixes\n"
            f"4. Prevention tips for similar issues"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def analyze_circuit(self, netlist: str, analysis_type: str, router) -> str:
        """Analyse un circuit SPICE existant."""
        prompt = (
            f"Analyze this SPICE circuit:\n\n"
            f"Netlist:\n{netlist}\n\n"
            f"Perform {analysis_type} analysis and provide:\n"
            f"1. Key circuit characteristics\n"
            f"2. Expected behavior\n"
            f"3. Critical parameters\n"
            f"4. Potential issues to watch for\n"
            f"5. Suggested measurements"
        )

        response = await self.run(prompt, router=router)
        return response.content

    async def explain_results(self, simulation_output: str, router) -> str:
        """Explique les résultats de simulation SPICE."""
        prompt = (
            f"Explain these SPICE simulation results:\n\n"
            f"{simulation_output}\n\n"
            f"Provide:\n"
            f"1. Summary of key findings\n"
            f"2. Circuit behavior explanation\n"
            f"3. Performance metrics\n"
            f"4. Potential improvements\n"
            f"5. Practical implications"
        )

        response = await self.run(prompt, router=router)
        return response.content


# Exemple d'utilisation
if __name__ == "__main__":
    # Cela nécessiterait un router configuré pour fonctionner
    agent = SpiceAgent()
    print(f"SPICE Agent created: {agent.name}")
    print(f"Description: {agent.description}")
    print(f"System prompt: {agent.system_prompt[:100]}...")
