"""AI-powered email summarization using OpenAI."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_random_exponential

from .tokenizer import count_tokens, segment_text
from ..utils.rate_limiter import RateLimiter

if TYPE_CHECKING:
    from ..config import Settings

logger = logging.getLogger(__name__)


@dataclass
class Summary:
    """Result of summarizing an email."""

    text: str
    action_items: list[str] = field(default_factory=list)
    estimated_tokens_used: int = 0


@dataclass
class Summarizer:
    """
    Email summarizer using OpenAI's chat completions API.
    
    Handles text segmentation, rate limiting, and multi-chunk summarization.
    """

    settings: Settings
    _client: OpenAI | None = field(default=None, init=False)
    _rate_limiter: RateLimiter | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        """Initialize OpenAI client and rate limiter."""
        self._client = OpenAI(api_key=self.settings.openai_api_key)
        self._rate_limiter = RateLimiter(
            tokens_per_minute=self.settings.token_limit_per_minute
        )

    @retry(
        wait=wait_random_exponential(min=1, max=60),
        stop=stop_after_attempt(6),
    )
    def _call_openai(self, prompt: str) -> str:
        """
        Make a rate-limited call to OpenAI API.
        
        Args:
            prompt: The prompt to send.
            
        Returns:
            The response content.
        """
        estimated_tokens = int(1.5 * count_tokens(prompt))
        self._rate_limiter.acquire(estimated_tokens)

        logger.debug(f"Calling OpenAI API with ~{estimated_tokens} tokens")

        response = self._client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
        )

        return response.choices[0].message.content or ""

    def summarize(self, email_content: str, sender: str = "") -> Summary:
        """
        Summarize an email, handling long content through chunking.
        
        Args:
            email_content: The email body to summarize.
            sender: Optional sender name for context.
            
        Returns:
            Summary object with text and action items.
        """
        # Segment the email if it's too long
        chunks = segment_text(
            email_content,
            max_tokens=self.settings.max_tokens_per_request,
            response_buffer=self.settings.response_buffer,
            context_buffer=self.settings.context_buffer,
        )

        logger.info(f"Processing email in {len(chunks)} chunk(s)")

        # Summarize each chunk
        chunk_summaries = []
        total_tokens = 0

        for i, chunk in enumerate(chunks, 1):
            prompt = self._build_chunk_prompt(chunk, i, len(chunks))
            summary = self._call_openai(prompt)
            chunk_summaries.append(summary)
            total_tokens += count_tokens(prompt) + count_tokens(summary)

            logger.debug(f"Chunk {i}/{len(chunks)} summarized")

        # If multiple chunks, consolidate into final summary
        if len(chunk_summaries) > 1:
            combined = "\n\n".join(chunk_summaries)
            final_prompt = self._build_consolidation_prompt(combined)
            final_summary = self._call_openai(final_prompt)
            total_tokens += count_tokens(final_prompt) + count_tokens(final_summary)
        else:
            final_summary = chunk_summaries[0] if chunk_summaries else ""

        return Summary(
            text=final_summary,
            estimated_tokens_used=total_tokens,
        )

    def _build_chunk_prompt(self, chunk: str, chunk_num: int, total_chunks: int) -> str:
        """Build prompt for summarizing a single chunk."""
        context = ""
        if total_chunks > 1:
            context = f"(Part {chunk_num} of {total_chunks}) "

        return f"""Summarize the following email {context}ensuring that:
1. Action items are listed with bullet points
2. Important dates, times, and locations are preserved
3. Key information is captured concisely

Also, identify any events in the format:
Event Detected: [Event Name] on [YYYY-MM-DD] at [HH:MM] at [Location]

Email content:
{chunk}"""

    def _build_consolidation_prompt(self, combined_summaries: str) -> str:
        """Build prompt for consolidating multiple chunk summaries."""
        return f"""Consolidate the following partial summaries into one coherent summary.
Ensure:
1. Bullet points are used for action items
2. All dates, times, and locations are preserved
3. Event Detected entries are preserved exactly
4. Remove any redundancy

Partial summaries:
{combined_summaries}"""
