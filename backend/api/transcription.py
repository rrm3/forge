"""Audio transcription API using Gemini 2.5 Flash."""

import logging
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from google import genai
from google.genai import types
from pydantic import BaseModel

from backend.auth import AuthUser
from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["transcription"])

# Maximum file size: 250MB (Gemini supports up to 2GB)
MAX_FILE_SIZE = 250 * 1024 * 1024

# Supported audio MIME types (browsers vary in what they send)
SUPPORTED_FORMATS = {
    "audio/wav",
    "audio/wave",
    "audio/x-wav",
    "audio/mp3",
    "audio/mpeg",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/webm",
    "audio/ogg",
    "audio/flac",
    "audio/aac",
    "audio/aiff",
    "audio/pcm",
}

# Extensions we accept when the browser sends a generic MIME type
SUPPORTED_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".mp4",
    ".webm",
    ".ogg",
    ".flac",
    ".aac",
    ".aiff",
    ".pcm",
}


class TranscriptionResponse(BaseModel):
    text: str


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    request: Request,
    file: Annotated[UploadFile, File(description="Audio file to transcribe")],
    _user: AuthUser = None,  # Require authentication
) -> TranscriptionResponse:
    """Transcribe audio file using Gemini 2.5 Flash."""
    # Check Content-Length header before reading file
    content_length = request.headers.get("content-length")
    try:
        if content_length and int(content_length) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail="File too large. Maximum size is 250MB.",
            )
    except ValueError:
        pass

    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File too large. Maximum size is 250MB.",
        )

    # Validate content type (fall back to extension for generic MIME types)
    ct = file.content_type or ""
    ext = (
        ("." + file.filename.rsplit(".", 1)[-1].lower())
        if file.filename and "." in file.filename
        else ""
    )
    if ct not in SUPPORTED_FORMATS and ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported audio format: {file.content_type}. "
            f"Supported formats: WAV, MP3, M4A, WebM, OGG, FLAC, AAC, AIFF",
        )

    if not settings.gemini_api_key:
        logger.error("Gemini API key not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transcription service not configured",
        )

    try:
        client = genai.Client(api_key=settings.gemini_api_key)

        logger.info("Transcribing audio: %s (%d bytes)", file.filename, len(content))

        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(
                            data=content,
                            mime_type=ct or (f"audio/{ext.lstrip('.')}" if ext else "audio/webm"),
                        ),
                        types.Part.from_text(
                            text="Transcribe this audio. Capture the speaker's intended "
                            "meaning faithfully, but clean up stutters, filler words "
                            "(um, uh), and self-corrections. Output only the transcribed "
                            "text, nothing else."
                        ),
                    ]
                )
            ],
        )

        text = response.text.strip() if response.text else ""
        logger.info("Transcription completed: %d characters", len(text))

        return TranscriptionResponse(text=text)

    except genai.errors.ClientError as e:
        if "RESOURCE_EXHAUSTED" in str(e) or "429" in str(e):
            logger.warning("Gemini rate limit exceeded")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Transcription service busy. Please try again in a moment.",
            ) from e
        if "UNAUTHENTICATED" in str(e) or "401" in str(e) or "403" in str(e):
            logger.error("Gemini authentication failed - check API key")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Transcription service not configured",
            ) from e
        logger.exception("Gemini API client error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription failed. Please try again.",
        ) from e
    except genai.errors.ServerError as e:
        logger.error("Gemini server error")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Transcription service unavailable. Please try again.",
        ) from e
    except Exception as e:
        logger.exception("Unexpected transcription error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transcription failed. Please try again.",
        ) from e
