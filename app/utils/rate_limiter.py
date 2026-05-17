"""Rate limiter implementation using token bucket algorithm."""

import asyncio
import time

from app.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter.

    Prevents API rate limit violations by controlling request rate.
    """

    def __init__(
        self,
        max_requests: int,
        period: int
    ):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed per period
            period: Time period in seconds
        """
        self.max_requests = max_requests
        self.period = period
        self.tokens = float(max_requests)
        self.last_refill = time.time()
        self._lock = asyncio.Lock()

        logger.info(
            "Rate limiter initialized",
            max_requests=max_requests,
            period=period
        )

    async def acquire(self, tokens: int = 1) -> None:
        """
        Wait until tokens are available.

        Args:
            tokens: Number of tokens to acquire (default: 1)
        """
        async with self._lock:
            while True:
                self._refill()

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    logger.debug(
                        "Token acquired",
                        tokens_remaining=self.tokens,
                        tokens_requested=tokens
                    )
                    return

                # Calculate wait time
                tokens_needed = tokens - self.tokens
                wait_time = (tokens_needed / self.max_requests) * self.period

                logger.debug(
                    "Rate limit reached, waiting",
                    wait_time=wait_time,
                    tokens_available=self.tokens,
                    tokens_needed=tokens_needed
                )

                await asyncio.sleep(wait_time)

    def _refill(self) -> None:
        """Refill tokens based on time elapsed."""
        now = time.time()
        elapsed = now - self.last_refill

        # Calculate tokens to add
        tokens_to_add = (elapsed / self.period) * self.max_requests

        if tokens_to_add > 0:
            self.tokens = min(self.max_requests, self.tokens + tokens_to_add)
            self.last_refill = now

            logger.debug(
                "Tokens refilled",
                tokens_added=tokens_to_add,
                tokens_available=self.tokens
            )

    @property
    def available_tokens(self) -> float:
        """Get current available tokens."""
        self._refill()
        return self.tokens

    def reset(self) -> None:
        """Reset rate limiter to full capacity."""
        self.tokens = float(self.max_requests)
        self.last_refill = time.time()
        logger.info("Rate limiter reset")

# Made with Bob
