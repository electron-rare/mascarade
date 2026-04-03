from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import tools, projects, ai, fabrication

app = FastAPI(title="MakeLife-CAD", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tools.router, prefix="/v1", tags=["tools"])
app.include_router(projects.router, prefix="/v1", tags=["projects"])
app.include_router(ai.router, prefix="/v1", tags=["ai"])
app.include_router(fabrication.router, prefix="/v1", tags=["fabrication"])


@app.get("/health")
async def health():
    return {"ok": True, "service": "makelife-cad", "version": "0.1.0"}
