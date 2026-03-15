"""Research agent — identifies and defines terms, jargon, and company references in real-time."""

import asyncio
import json
import time
from typing import Callable, Awaitable

import anthropic

from .config import ANTHROPIC_API_KEY
from .research_prompts import RESEARCH_SYSTEM_PROMPT
from .stt_base import TranscriptSegment

RESEARCH_INTERVAL_SEC = 20
RESEARCH_MODEL = "claude-sonnet-4-20250514"
CARD_TTL_SEC = 60
MAX_VISIBLE_CARDS = 3


class ResearchAgent:
    def __init__(self, on_cards: Callable[[list[dict]], Awaitable[None]]):
        self._client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        self._transcript: list[TranscriptSegment] = []
        self._last_analysis_idx = 0
        self._last_analysis_time = 0.0
        self._on_cards = on_cards
        self._running = False
        self._task = None
        self._active_cards: list[dict] = []

    async def start(self) -> None:
        self._running = True
        self._last_analysis_time = time.time()
        self._task = asyncio.create_task(self._analysis_loop())

    async def add_segment(self, segment: TranscriptSegment) -> None:
        self._transcript.append(segment)

    async def _analysis_loop(self):
        while self._running:
            await asyncio.sleep(2)

            now = time.time()

            # Expire old cards
            self._active_cards = [
                c for c in self._active_cards
                if now - c.get("_created", 0) < CARD_TTL_SEC
            ]

            new_segments = self._transcript[self._last_analysis_idx:]
            if not new_segments:
                continue

            if now - self._last_analysis_time < RESEARCH_INTERVAL_SEC:
                continue

            await self._analyze(new_segments)
            self._last_analysis_idx = len(self._transcript)
            self._last_analysis_time = now

    async def _analyze(self, new_segments: list[TranscriptSegment]):
        new_text = "\n".join(f"[{seg.speaker}] {seg.text}" for seg in new_segments)

        user_msg = f"""Recent interview dialogue:

{new_text}

Identify any terms, companies, or jargon worth defining for the candidate. Return JSON array."""

        try:
            response = await self._client.messages.create(
                model=RESEARCH_MODEL,
                max_tokens=400,
                system=RESEARCH_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )

            text = response.content[0].text.strip()

            if text.startswith("["):
                cards = json.loads(text)
            else:
                start = text.find("[")
                end = text.rfind("]") + 1
                if start >= 0 and end > start:
                    cards = json.loads(text[start:end])
                else:
                    cards = []

            if cards:
                now = time.time()
                for card in cards:
                    card["_created"] = now

                self._active_cards = (cards + self._active_cards)[:MAX_VISIBLE_CARDS]
                await self._on_cards(self._active_cards)

        except Exception as e:
            print(f"Research agent error: {e}")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
