import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()

# Modèle de réponse pour /api/models
class ModelInfo(BaseModel):
    name: str
    description: Optional[str] = None
    size: Optional[int] = None
    quantization_level: Optional[str] = None

# Modèle de requête pour /api/generate
class GenerateRequest(BaseModel):
    model: str
    prompt: str
    stream: Optional[bool] = False
    options: Optional[dict] = None

# Modèle de réponse pour /api/generate
class GenerateResponse(BaseModel):
    model: str
    created_at: str
    response: str
    done: bool

@app.get("/api/models")
def list_models():
    # Fake: retourne un modèle "mascarade"
    return {"models": [ModelInfo(name="mascarade", description="Mascarade LLM proxy").dict()]}

@app.post("/api/generate")
def generate_text(req: GenerateRequest):
    # Fake: proxy vers Mascarade ou réponse simulée
    # Ici, on retourne une réponse factice
    return GenerateResponse(
        model=req.model,
        created_at="2026-03-22T00:00:00Z",
        response=f"[Mascarade fake Ollama] Réponse à: {req.prompt}",
        done=True
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=11434)
