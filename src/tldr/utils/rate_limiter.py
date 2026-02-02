"""Thread-safe token rate limiter for API calls."""

from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    """
    Token-based rate limiter with sliding window.
    
    Thread-safe for sync usage, also supports async.
    """

    tokens_per_minute: int = 180_000
    _tokens_used: int = field(default=0, init=False)
    _window_start: float = field(default_factory=time.time, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _async_lock: asyncio.Lock | None = field(default=None, init=False)

    def _reset_if_needed(self) -> None:
        """Reset the window if a minute has passed."""
        now = time.time()
        if now - self._window_start >= 60:
            self._tokens_used = 0
            self._window_start = now

    def acquire(self, tokens: int) -> None:
        """
        Acquire tokens, blocking if rate limit would be exceeded.
        
        Args:
            tokens: Number of tokens to acquire.
        """
        with self._lock:
            self._reset_if_needed()

            if self._tokens_used + tokens > self.tokens_per_minute:
                # Calculate sleep time until window resets
                elapsed = time.time() - self._window_start
                sleep_time = max(0, 60 - elapsed)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    self._tokens_used = 0
                    self._window_start = time.time()

            self._tokens_used += tokens

    async def acquire_async(self, tokens: int) -> None:
        """
        Async version of acquire.
        
        Args:
            tokens: Number of tokens to acquire.
        """
        if self._async_lock is None:
            self._async_lock = asyncio.Lock()

        async with self._async_lock:
            self._reset_if_needed()

            if self._tokens_used + tokens > self.tokens_per_minute:
                elapsed = time.time() - self._window_start
                sleep_time = max(0, 60 - elapsed)
                
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    self._tokens_used = 0
                    self._window_start = time.time()

            self._tokens_used += tokens

    @property
    def tokens_remaining(self) -> int:
        """Get remaining tokens in current window."""
        with self._lock:
            self._reset_if_needed()
            return max(0, self.tokens_per_minute - self._tokens_used)
