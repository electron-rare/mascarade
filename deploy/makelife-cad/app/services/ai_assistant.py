import os
import httpx

RAG_URL = os.getenv("RAG_URL", "http://192.168.0.120:8100")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_FALLBACK_URL = os.getenv("OLLAMA_FALLBACK_URL", "http://localhost:11435")
PRIMARY_MODEL = os.getenv("PRIMARY_MODEL", "mellum-4b")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "qwen3:8b")

SYSTEM_BASE = (
    "You are a PCB design assistant specializing in KiCad. "
    "Answer questions about electronic components, circuit design, "
    "and PCB layout. Be precise with part numbers and values."
)


class AIAssistant:
    def __init__(self):
        self._rag = httpx.AsyncClient(base_url=RAG_URL, timeout=30.0)
        self._primary = httpx.AsyncClient(
            base_url=OLLAMA_URL, timeout=60.0
        )
        self._fallback = httpx.AsyncClient(
            base_url=OLLAMA_FALLBACK_URL, timeout=60.0
        )

    async def chat(
        self, message: str, project_context: str = ""
    ) -> dict:
        rag_ctx = await self._get_rag_context(message)
        system = self._build_prompt(rag_ctx, project_context)
        response = await self._generate(system, message)
        return {
            "response": response,
            "sources": rag_ctx.get("sources", []),
        }

    async def _get_rag_context(self, query: str) -> dict:
        try:
            resp = await self._rag.post(
                "/v1/api/rag/query",
                json={
                    "query": query,
                    "collection": "datasheets",
                    "top_k": 3,
                },
            )
            if resp.status_code == 200:
                return resp.json()
        except httpx.HTTPError:
            pass
        return {"context": "", "sources": []}

    def _build_prompt(
        self, rag_ctx: dict, project_ctx: str
    ) -> str:
        parts = [SYSTEM_BASE]
        ctx = rag_ctx.get("context", "")
        if ctx:
            parts.append(f"Datasheet context:\n{ctx}")
        if project_ctx:
            parts.append(f"Current project:\n{project_ctx}")
        return "\n\n".join(parts)

    async def _generate(self, system: str, message: str) -> str:
        models = [
            (self._primary, PRIMARY_MODEL),
            (self._fallback, FALLBACK_MODEL),
        ]
        for client, model in models:
            try:
                resp = await client.post(
                    "/api/generate",
                    json={
                        "model": model,
                        "prompt": message,
                        "system": system,
                        "stream": False,
                    },
                )
                if resp.status_code == 200:
                    return resp.json().get("response", "")
            except httpx.HTTPError:
                continue
        return "AI unavailable. All models failed."


ai_assistant = AIAssistant()
