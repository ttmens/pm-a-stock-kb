"""Base collector class with common functionality."""
import hashlib
import time
import random
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class RawEvent:
    """Raw event from data source."""
    stock_code: str
    event_type: str  # announcement/financial/capital/social/policy/research
    event_time: str  # ISO format
    title: str
    content: str
    source: str
    source_url: str = ""
    raw_json: Dict[str, Any] = field(default_factory=dict)
    sentiment_score: float = 0.0

    @property
    def content_hash(self) -> str:
        """SHA-256 hash for dedup."""
        raw = f"{self.stock_code}-{self.title}-{self.event_time}-{self.source}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Convert to dict for DB insertion."""
        d = asdict(self)
        d["content_hash"] = self.content_hash
        return d


@dataclass
class RawFactor:
    """Raw factor data from data source."""
    stock_code: str
    factor_date: str  # YYYY-MM-DD
    factor_name: str
    factor_value: float
    factor_source: str = ""

    @property
    def content_hash(self) -> str:
        raw = f"{self.stock_code}-{self.factor_date}-{self.factor_name}-{self.factor_source}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["content_hash"] = self.content_hash
        return d


class BaseCollector(ABC):
    """Base class for all data collectors.

    Features:
    - Rate limiting (1-3s between requests)
    - Retry with exponential backoff (max 3 attempts)
    - Hash-based dedup
    - Structured logging
    - User-Agent rotation
    """

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    ]

    def __init__(self, name: str, rate_limit: tuple = (1.0, 3.0), max_retries: int = 3):
        self.name = name
        self.rate_limit = rate_limit  # (min_seconds, max_seconds)
        self.max_retries = max_retries
        self._client: Optional[httpx.Client] = None
        self._seen_hashes: set = set()

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": random.choice(self.USER_AGENTS)},
            )
        return self._client

    def _rate_limit_wait(self):
        """Wait between requests to avoid being blocked."""
        delay = random.uniform(*self.rate_limit)
        time.sleep(delay)

    def _get_with_retry(self, url: str, params: dict = None, headers: dict = None) -> Optional[httpx.Response]:
        """HTTP GET with retry and exponential backoff."""
        for attempt in range(self.max_retries):
            try:
                self._rate_limit_wait()
                resp = self.client.get(url, params=params, headers=headers)
                resp.raise_for_status()
                return resp
            except Exception as e:
                wait = (2 ** attempt) + random.random()
                logger.warning(f"[{self.name}] Attempt {attempt+1}/{self.max_retries} failed for {url}: {e}. Waiting {wait:.1f}s")
                if attempt < self.max_retries - 1:
                    time.sleep(wait)
        logger.error(f"[{self.name}] All {self.max_retries} attempts failed for {url}")
        return None

    def _is_duplicate(self, event: RawEvent) -> bool:
        """Check if event is duplicate based on content hash."""
        h = event.content_hash
        if h in self._seen_hashes:
            return True
        self._seen_hashes.add(h)
        return False

    @abstractmethod
    def collect_events(self, stock_codes: List[str] = None) -> List[RawEvent]:
        """Collect raw events. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def collect_factors(self, stock_codes: List[str] = None) -> List[RawFactor]:
        """Collect raw factor data. Must be implemented by subclasses."""
        pass

    def collect_all(self, stock_codes: List[str] = None) -> dict:
        """Collect both events and factors, with dedup."""
        self._seen_hashes.clear()

        events = []
        for e in self.collect_events(stock_codes):
            if not self._is_duplicate(e):
                events.append(e.to_dict())

        factors = []
        for f in self.collect_factors(stock_codes):
            h = f.content_hash
            if h not in self._seen_hashes:
                self._seen_hashes.add(h)
                factors.append(f.to_dict())

        logger.info(f"[{self.name}] Collected {len(events)} events, {len(factors)} factors")
        return {"events": events, "factors": factors}

    def close(self):
        """Close HTTP client."""
        if self._client:
            self._client.close()
            self._client = None
