"""FastAPI router — RAG multi-tool orchestration endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
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
    chunk: bool = False  # auto-chunk each document using rag_chunk_size/overlap settings
    contextual_retrieval: bool | None = None


class RAGIngestResponse(BaseModel):
    ingested: int
    collection: str


class RAGIngestURLRequest(BaseModel):
    url: str
    collection: str | None = None
    model: str = "text-embedding-3-small"
    chunk_size: int | None = None  # None = use settings.rag_chunk_size
    chunk_overlap: int | None = None
    metadata: dict[str, Any] = {}
    ocr: bool = False
    contextual_retrieval: bool | None = None


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
        docs = body.documents
        if body.chunk:
            from mascarade.config import settings as _settings
            from mascarade.rag.chunker import chunk_document

            chunked: list[dict[str, Any]] = []
            for doc in docs:
                chunked.extend(
                    chunk_document(doc, _settings.rag_chunk_size, _settings.rag_chunk_overlap)
                )
            docs = chunked or docs

        count = await pipeline.ingest(
            docs,
            model=body.model,
            collection=body.collection,
            contextual_retrieval=body.contextual_retrieval,
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
    """List all Qdrant collections with point counts."""
    vs = QdrantVectorStore()
    try:
        raw = await vs.list_collections()
        collections = []
        for c in raw:
            name = c.get("name", "unknown")
            # Fetch per-collection info for point counts
            col_vs = QdrantVectorStore(collection=name)
            try:
                info = await col_vs.collection_info()
                collections.append(
                    CollectionInfo(
                        name=name,
                        vectors_count=info.get("vectors_count"),
                        points_count=info.get("points_count"),
                    )
                )
            except Exception:
                collections.append(CollectionInfo(name=name))
            finally:
                await col_vs.close()
        return CollectionsResponse(collections=collections)
    except Exception as exc:
        logger.exception("Failed to list Qdrant collections")
        raise HTTPException(status_code=502, detail=f"Qdrant error: {exc}") from exc
    finally:
        await vs.close()


@router.get("/collections/{name}", response_model=CollectionInfo)
async def rag_collection_info(name: str) -> CollectionInfo:
    """Get info (point count) for a specific Qdrant collection."""
    vs = QdrantVectorStore(collection=name)
    try:
        info = await vs.collection_info()
        return CollectionInfo(
            name=name,
            vectors_count=info.get("vectors_count"),
            points_count=info.get("points_count"),
        )
    except Exception as exc:
        if "404" in str(exc) or "not found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=f"Collection {name!r} not found") from exc
        logger.exception("Failed to get collection info")
        raise HTTPException(status_code=502, detail=f"Qdrant error: {exc}") from exc
    finally:
        await vs.close()


@router.delete("/collections/{name}")
async def rag_collection_delete(name: str) -> dict[str, Any]:
    """Delete a Qdrant collection and all its documents.

    This is irreversible. Use with caution.
    """
    if name in {"rag-query-cache"}:
        raise HTTPException(
            status_code=403,
            detail=f"Collection {name!r} is reserved and cannot be deleted via this endpoint",
        )
    vs = QdrantVectorStore(collection=name)
    try:
        deleted = await vs.drop_collection()
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Collection {name!r} not found")
        return {"deleted": True, "collection": name}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete collection")
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


# ---------------------------------------------------------------------------
# URL / file ingestion (Docling-powered)
# ---------------------------------------------------------------------------


async def _ingest_text_via_pipeline(
    pipeline: RAGPipeline,
    text: str,
    source: str,
    body_model: str,
    body_collection: str | None,
    body_chunk_size: int | None,
    body_chunk_overlap: int | None,
    body_metadata: dict[str, Any],
    body_contextual_retrieval: bool | None,
) -> RAGIngestResponse:
    """Shared helper: chunk + ingest text content."""
    from mascarade.config import settings as _settings
    from mascarade.rag.chunker import chunk_document

    doc: dict[str, Any] = {"text": text, "source": source, **body_metadata}
    chunk_size = body_chunk_size or _settings.rag_chunk_size
    chunk_overlap = body_chunk_overlap or _settings.rag_chunk_overlap
    docs = chunk_document(doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap) or [doc]

    count = await pipeline.ingest(
        docs,
        model=body_model,
        collection=body_collection,
        contextual_retrieval=body_contextual_retrieval,
    )
    collection_name = body_collection or pipeline.vectorstore.collection
    return RAGIngestResponse(ingested=count, collection=collection_name)


@router.post("/ingest/url", response_model=RAGIngestResponse)
async def rag_ingest_url(body: RAGIngestURLRequest, request: Request) -> RAGIngestResponse:
    """Fetch, parse, chunk and ingest a remote document URL via Docling.

    Requires ``DOCLING_URL`` to be configured (mascarade-docling service).
    Supports PDF, DOCX, HTML, Markdown, and more.

    With ``ocr=true``, enables OCR for scanned PDFs (slower, requires Docling GPU).
    """
    from mascarade.mcp.docling import get_client as get_docling

    docling = get_docling()
    if docling is None:
        raise HTTPException(
            status_code=503,
            detail="Docling not configured — set DOCLING_URL in environment",
        )

    pipeline = _get_pipeline(request)
    try:
        result = await docling.convert_url(body.url, ocr=body.ocr)
        text = result.get("content", "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="Docling returned empty content for URL")

        doc_metadata = {**body.metadata, "docling_metadata": result.get("metadata", {})}
        return await _ingest_text_via_pipeline(
            pipeline,
            text=text,
            source=body.url,
            body_model=body.model,
            body_collection=body.collection,
            body_chunk_size=body.chunk_size,
            body_chunk_overlap=body.chunk_overlap,
            body_metadata=doc_metadata,
            body_contextual_retrieval=body.contextual_retrieval,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("RAG ingest/url failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await pipeline.close()


@router.post("/ingest/upload", response_model=RAGIngestResponse)
async def rag_ingest_upload(
    request: Request,
    file: UploadFile = File(...),
    collection: str | None = None,
    model: str = "text-embedding-3-small",
    ocr: bool = False,
    contextual_retrieval: bool | None = None,
) -> RAGIngestResponse:
    """Upload, parse, chunk and ingest a local file via Docling.

    Accepts any file type supported by Docling (PDF, DOCX, PPTX, HTML, …).
    File size limit: 50 MB.

    Requires ``DOCLING_URL`` to be configured (mascarade-docling service).
    """
    from mascarade.config import settings as _settings
    from mascarade.mcp.docling import get_client as get_docling

    docling = get_docling()
    if docling is None:
        raise HTTPException(
            status_code=503,
            detail="Docling not configured — set DOCLING_URL in environment",
        )

    max_bytes = 50 * 1024 * 1024  # 50 MB
    content_bytes = await file.read(max_bytes + 1)
    if len(content_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit")

    mime_type = file.content_type or "application/octet-stream"
    pipeline = _get_pipeline(request)
    try:
        result = await docling.convert_text(
            content_bytes.decode("utf-8", errors="replace"),
            mime_type=mime_type,
        )
        text = result.get("content", "").strip()
        if not text:
            raise HTTPException(status_code=422, detail="Docling returned empty content for file")

        return await _ingest_text_via_pipeline(
            pipeline,
            text=text,
            source=file.filename or "upload",
            body_model=model,
            body_collection=collection,
            body_chunk_size=_settings.rag_chunk_size,
            body_chunk_overlap=_settings.rag_chunk_overlap,
            body_metadata={"filename": file.filename, "mime_type": mime_type},
            body_contextual_retrieval=contextual_retrieval,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("RAG ingest/upload failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        await pipeline.close()
