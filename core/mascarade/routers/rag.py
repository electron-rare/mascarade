"""FastAPI router — RAG multi-tool orchestration endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from mascarade.rag.embeddings import EmbeddingProvider
from mascarade.rag.pipeline import RAGPipeline
from mascarade.rag.vectorstore import QdrantVectorStore

logger = logging.getLogger("mascarade.routers.rag")

router = APIRouter(tags=["rag"], prefix="/v1/api/rag")

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class RAGQueryRequest(BaseModel):
    query: str
    tools: list[str] | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float | None = None
    provider: str | None = None
    model: str | None = None
    collection: str | None = None
    skip_classification: bool = False


class RAGQueryResponse(BaseModel):
    answer: str
    intent: str
    sources: list[dict[str, Any]]
    tool_calls: list[str]
    provider: str | None = None
    model: str | None = None
    usage: dict[str, int] = {}
    elapsed_seconds: float = 0.0


class RAGIngestRequest(BaseModel):
    documents: list[dict[str, Any]]
    model: str = "text-embedding-3-small"
    collection: str | None = None


class RAGIngestResponse(BaseModel):
    ingested: int
    collection: str


class RAGSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float | None = None
    collection: str | None = None
    filters: dict[str, Any] | None = None
    model: str = "text-embedding-3-small"


class RAGSearchResponse(BaseModel):
    results: list[dict[str, Any]]
    collection: str


class CollectionInfo(BaseModel):
    name: str
    vectors_count: int | None = None
    points_count: int | None = None


class CollectionsResponse(BaseModel):
    collections: list[CollectionInfo]


class RAGEvalItem(BaseModel):
    question: str
    ground_truth: str = ""
    answer: str = ""
    contexts: list[str] = []


class RAGEvalRequest(BaseModel):
    dataset: list[RAGEvalItem]
    run_pipeline: bool = True  # fill missing answers/contexts via pipeline
    judge_provider: str | None = None
    judge_model: str | None = None


class RAGEvalResponse(BaseModel):
    metrics: dict[str, float]
    thresholds: dict[str, float]
    status: dict[str, str]
    overall: str
    n_items: int
    n_errors: int
    elapsed_seconds: float


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_pipeline(request: Request) -> RAGPipeline:
    """Build a RAGPipeline from the application state."""
    llm_router = request.app.state.router
    if llm_router is None:
        raise HTTPException(status_code=503, detail="LLM router not initialised")
    embeddings = EmbeddingProvider()
    vectorstore = QdrantVectorStore()
    return RAGPipeline(router=llm_router, vectorstore=vectorstore, embeddings=embeddings)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(body: RAGQueryRequest, request: Request) -> RAGQueryResponse:
    """RAG query with optional tool selection and intent classification."""
    pipeline = _get_pipeline(request)
    try:
        result = await pipeline.query(
            body.query,
            tools=body.tools,
            top_k=body.top_k,
            score_threshold=body.score_threshold,
            provider=body.provider,
            model=body.model,
            collection=body.collection,
            skip_classification=body.skip_classification,
        )
        return RAGQueryResponse(**result)
    except Exception as exc:
        logger.exception("RAG query failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await pipeline.close()


@router.post("/ingest", response_model=RAGIngestResponse)
async def rag_ingest(body: RAGIngestRequest, request: Request) -> RAGIngestResponse:
    """Ingest documents into the vector store for future retrieval."""
    if not body.documents:
        raise HTTPException(status_code=400, detail="No documents provided")

    pipeline = _get_pipeline(request)
    try:
        count = await pipeline.ingest(
            body.documents,
            model=body.model,
            collection=body.collection,
        )
        collection_name = body.collection or pipeline.vectorstore.collection
        return RAGIngestResponse(ingested=count, collection=collection_name)
    except Exception as exc:
        logger.exception("RAG ingest failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await pipeline.close()


@router.get("/collections", response_model=CollectionsResponse)
async def rag_collections() -> CollectionsResponse:
    """List all Qdrant collections."""
    vs = QdrantVectorStore()
    try:
        raw = await vs.list_collections()
        collections = [CollectionInfo(name=c.get("name", "unknown")) for c in raw]
        return CollectionsResponse(collections=collections)
    except Exception as exc:
        logger.exception("Failed to list Qdrant collections")
        raise HTTPException(status_code=502, detail=f"Qdrant error: {exc}") from exc
    finally:
        await vs.close()


@router.post("/search", response_model=RAGSearchResponse)
async def rag_search(body: RAGSearchRequest) -> RAGSearchResponse:
    """Direct vector search without LLM generation."""
    collection_name = body.collection or "mascarade-rag"
    vs = QdrantVectorStore(collection=collection_name)
    embeddings = EmbeddingProvider()
    try:
        query_embedding = await embeddings.embed_query(body.query, model=body.model)
        results = await vs.search(
            query_embedding,
            top_k=body.top_k,
            score_threshold=body.score_threshold,
            filters=body.filters,
        )
        return RAGSearchResponse(results=results, collection=collection_name)
    except Exception as exc:
        logger.exception("RAG search failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await vs.close()
        await embeddings.close()


@router.post("/eval", response_model=RAGEvalResponse)
async def rag_eval(body: RAGEvalRequest, request: Request) -> RAGEvalResponse:
    """Evaluate RAG pipeline quality against a golden dataset.

    Computes RAGAS-compatible metrics (Faithfulness, Answer Relevance,
    Context Precision, Context Recall, Hallucination Rate) using LLM judges.

    Pass ``run_pipeline=true`` to let the pipeline fill missing answers/contexts.
    """
    from mascarade.rag.eval import RAGEvaluator

    if not body.dataset:
        raise HTTPException(status_code=400, detail="Empty dataset")

    pipeline = _get_pipeline(request)
    try:
        evaluator = RAGEvaluator(
            pipeline,
            judge_provider=body.judge_provider,
            judge_model=body.judge_model,
        )
        result = await evaluator.evaluate(
            [item.model_dump() for item in body.dataset],
            run_pipeline=body.run_pipeline,
        )
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return RAGEvalResponse(**{k: result[k] for k in RAGEvalResponse.model_fields})
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("RAG eval failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await pipeline.close()
