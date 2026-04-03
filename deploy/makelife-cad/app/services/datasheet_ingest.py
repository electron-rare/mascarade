import os
import httpx

RAG_URL = os.getenv("RAG_URL", "http://192.168.0.120:8100")


class DatasheetIngestor:
    def __init__(self):
        self._client = httpx.AsyncClient(base_url=RAG_URL, timeout=60.0)

    async def ingest(self, filename: str, content: bytes) -> dict:
        resp = await self._client.post(
            "/v1/api/rag/ingest",
            files={"file": (filename, content, "application/pdf")},
            data={"collection": "datasheets"},
        )
        resp.raise_for_status()
        return resp.json()

    async def ingest_batch(
        self, files: list[tuple[str, bytes]]
    ) -> list[dict]:
        results = []
        for filename, content in files:
            result = await self.ingest(filename, content)
            results.append(result)
        return results


datasheet_ingestor = DatasheetIngestor()
