import os
import httpx

DOLIBARR_URL = os.getenv(
    "DOLIBARR_URL", "http://192.168.0.120:8488"
)
DOLIBARR_API_KEY = os.getenv("DOLIBARR_API_KEY", "doli2026")


class DolibarrBOMSync:
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=DOLIBARR_URL,
            headers={"DOLAPIKEY": DOLIBARR_API_KEY},
            timeout=15.0,
        )

    async def check_stock(
        self, components: list[dict]
    ) -> list[dict]:
        results = []
        for comp in components:
            ref = comp.get("reference", comp.get("value", ""))
            stock = await self._get_stock(ref)
            results.append(
                {
                    **comp,
                    "dolibarr_stock": stock.get("stock_reel", 0),
                    "dolibarr_id": stock.get("id"),
                    "in_stock": stock.get("stock_reel", 0) > 0,
                }
            )
        return results

    async def _get_stock(self, ref: str) -> dict:
        try:
            resp = await self._client.get(
                "/api/index.php/products",
                params={"sqlfilters": f"(t.ref:like:'{ref}%')"},
            )
            if resp.status_code == 200:
                products = resp.json()
                if products:
                    return products[0]
        except httpx.HTTPError:
            pass
        return {}


dolibarr_bom = DolibarrBOMSync()
