"""FastAPI endpoints for TLDR service."""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from .config import get_settings, Settings
from .ai import Summarizer
from .calendar import detect_events, DetectedEvent


# Pydantic models for API
class SummarizeRequest(BaseModel):
    """Request body for summarization."""

    text: str
    sender: Optional[str] = None


class EventResponse(BaseModel):
    """Event in API response."""

    name: str
    date: str
    time: str
    location: str
    calendar_link: str


class SummarizeResponse(BaseModel):
    """Response for summarization."""

    summary: str
    events: list[EventResponse]
    tokens_used: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str


# API key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key(
    api_key: str | None = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> str | None:
    """Validate API key if configured."""
    if settings.api_key and api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="TLDR - Email Summarizer API",
        description="AI-powered email summarization with event detection",
        version="2.0.0",
    )

    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """Health check endpoint."""
        return HealthResponse(status="healthy", version="2.0.0")

    @app.post("/api/summarize", response_model=SummarizeResponse)
    async def summarize(
        request: SummarizeRequest,
        _: str | None = Depends(get_api_key),
        settings: Settings = Depends(get_settings),
    ) -> SummarizeResponse:
        """
        Summarize text and detect events.
        
        Returns a concise summary with action items and calendar links for any
        detected events.
        """
        summarizer = Summarizer(settings=settings)
        result = summarizer.summarize(request.text, sender=request.sender or "")

        # Detect events
        events = detect_events(result.text)
        event_responses = [
            EventResponse(
                name=e.name,
                date=e.date,
                time=e.time,
                location=e.location,
                calendar_link=e.calendar_link,
            )
            for e in events
        ]

        return SummarizeResponse(
            summary=result.text,
            events=event_responses,
            tokens_used=result.estimated_tokens_used,
        )

    return app


# For direct uvicorn usage
app = create_app()
