
import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

# Modèle de réponse pour /api/models
class ModelInfo(BaseModel):
    name: str
    description: str | None = None
    size: int | None = None
    quantization_level: str | None = None

# Modèle de requête pour /api/generate
class GenerateRequest(BaseModel):
    model: str
    prompt: str
    stream: bool | None = False
    options: dict | None = None

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
