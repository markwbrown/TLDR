"""Token counting and text segmentation utilities."""

from __future__ import annotations

import tiktoken

# Cache the encoding for reuse
_encoding: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    """Get or create the tiktoken encoding."""
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding("cl100k_base")
    return _encoding


def count_tokens(text: str) -> int:
    """
    Count the number of tokens in a text string.
    
    Args:
        text: The text to count tokens for.
        
    Returns:
        Number of tokens.
    """
    encoding = _get_encoding()
    return len(encoding.encode(text))


def segment_text(
    text: str,
    max_tokens: int,
    response_buffer: int = 100,
    context_buffer: int = 200,
    previous_context: str = "",
) -> list[str]:
    """
    Segment text into chunks that fit within token limits.
    
    Uses a binary search approach to find optimal split points.
    
    Args:
        text: The text to segment.
        max_tokens: Maximum tokens per segment.
        response_buffer: Tokens reserved for response.
        context_buffer: Tokens reserved for context.
        previous_context: Any previous context to account for.
        
    Returns:
        List of text segments.
    """
    total_buffer = response_buffer
    
    if previous_context:
        total_buffer += context_buffer
        combined_tokens = count_tokens(text) + count_tokens(previous_context)
    else:
        combined_tokens = count_tokens(text)

    # If it fits, return as single segment
    if combined_tokens <= max_tokens - response_buffer:
        return [text]

    # Otherwise, split using binary search
    available_tokens = max_tokens - total_buffer
    return _binary_search_split(text, available_tokens)


def _binary_search_split(text: str, max_tokens: int) -> list[str]:
    """
    Split text using binary search to find optimal break points.
    
    Args:
        text: Text to split.
        max_tokens: Maximum tokens per segment.
        
    Returns:
        List of text segments.
    """
    if count_tokens(text) <= max_tokens:
        return [text]

    low, high = 0, len(text)
    mid_point = (low + high) // 2

    while low < mid_point:
        current_subtext = text[low:mid_point]
        if count_tokens(current_subtext) > max_tokens:
            high = mid_point
        else:
            low = mid_point

        new_mid = (low + high) // 2
        if new_mid == mid_point:
            break
        mid_point = new_mid

    # Try to break at a natural boundary (space, newline)
    break_point = mid_point
    for i in range(mid_point, max(0, mid_point - 50), -1):
        if text[i] in (' ', '\n', '.', '!', '?'):
            break_point = i + 1
            break

    segments = [text[:break_point].strip()]
    remaining = text[break_point:].strip()
    
    if remaining:
        segments.extend(_binary_search_split(remaining, max_tokens))

    return segments
