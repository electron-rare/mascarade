"""FastAPI router for Mistral Document AI and Audio Transcription."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from mascarade.auth import require_auth

logger = logging.getLogger("mascarade.routers.mistral_capabilities")

router = APIRouter(
    prefix="/v1/api/mistral",
    dependencies=[Depends(require_auth)],
    tags=["mistral-capabilities"],
)


# ---------------------------------------------------------------------------
# Document AI
# ---------------------------------------------------------------------------

@router.post("/document")
async def process_document(
    file: UploadFile = File(..., description="PDF, image, or office document"),
    prompt: Annotated[str, Form()] = "",
    include_image_base64: Annotated[bool, Form()] = False,
    table_format: Annotated[str | None, Form()] = None,
):
    """Process a document with Mistral Document AI (OCR + optional Q&A).

    Upload a PDF, image (PNG/JPEG/AVIF), PPTX, or DOCX file.
    Optionally provide a *prompt* to ask a question about the document.
    """
    from mascarade.integrations.mistral_capabilities import MistralDocumentAI

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    # Write to temp file
    import tempfile
    from pathlib import Path

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        doc_ai = MistralDocumentAI()
        result = await doc_ai.process_document(
            tmp_path,
            prompt=prompt,
            include_image_base64=include_image_base64,
            table_format=table_format,
        )
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Document processing failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        import os
        os.unlink(tmp_path)


@router.post("/ocr")
async def ocr_image(
    file: UploadFile = File(..., description="Image file (PNG, JPEG, AVIF)"),
):
    """Extract text from an image using Mistral OCR.

    Returns the extracted markdown text.
    """
    from mascarade.integrations.mistral_capabilities import MistralDocumentAI

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    import tempfile
    from pathlib import Path

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        doc_ai = MistralDocumentAI()
        text = await doc_ai.ocr(tmp_path)
        return {"text": text, "filename": file.filename}
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("OCR failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        import os
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Audio Transcription
# ---------------------------------------------------------------------------

@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(..., description="Audio file (mp3, wav, m4a, flac, ogg, webm)"),
    language: Annotated[str, Form()] = "fr",
    diarize: Annotated[bool, Form()] = False,
):
    """Transcribe an audio file using Mistral Voxtral.

    Upload an audio file and receive the transcription text.
    """
    from mascarade.integrations.mistral_capabilities import MistralAudioTranscription

    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    try:
        audio_bytes = await file.read()
        transcriber = MistralAudioTranscription()
        result = await transcriber.transcribe_bytes(
            audio_bytes,
            filename=file.filename,
            language=language,
            diarize=diarize,
        )
        return result
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Transcription failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
