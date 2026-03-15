"""Claude-powered real-time coaching engine."""

import asyncio
import json
import time
from typing import Callable, Awaitable

import anthropic

from .config import ANTHROPIC_API_KEY, COACHING_INTERVAL_SEC, COACHING_MODEL, SYSTEM_PROMPT
from .stt_base import TranscriptSegment
from .knowledge_base import KnowledgeBase


class CoachingEngine:
    def __init__(self, on_cards: Callable[[list[dict]], Awaitable[None]], knowledge_base: KnowledgeBase | None = None):
        self._client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
        self._transcript: list[TranscriptSegment] = []
        self._last_analysis_idx = 0
        self._last_analysis_time = 0.0
        self._on_cards = on_cards
        self._running = False
        self._task = None
        self._kb = knowledge_base

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
            new_segments = self._transcript[self._last_analysis_idx:]

            if not new_segments:
                continue

            time_since_last = now - self._last_analysis_time
            if time_since_last < COACHING_INTERVAL_SEC:
                continue

            await self._analyze(new_segments)
            self._last_analysis_idx = len(self._transcript)
            self._last_analysis_time = now

    async def _analyze(self, new_segments: list[TranscriptSegment]):
        # Build conversation context
        full_transcript = "\n".join(
            f"[{seg.speaker}] {seg.text}" for seg in self._transcript
        )

        new_text = "\n".join(
            f"[{seg.speaker}] {seg.text}" for seg in new_segments
        )

        # Search knowledge base for relevant context
        kb_section = ""
        if self._kb:
            query = " ".join(seg.text for seg in new_segments[-5:])
            try:
                chunks = self._kb.search(query, top_k=3)
                if chunks:
                    kb_section = "\n\n## Relevant Context From Research\n" + "\n---\n".join(chunks)
            except Exception as e:
                print(f"KB search error: {e}")

        user_msg = f"""## Full Transcript So Far
{full_transcript}

## New Content (analyze this for coaching opportunities)
{new_text}{kb_section}

Provide coaching cards as JSON array. Return [] if no coaching needed.
You may also use type REFERENCE for cards that surface directly relevant info from the research context."""

        try:
            response = await self._client.messages.create(
                model=COACHING_MODEL,
                max_tokens=500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )

            text = response.content[0].text.strip()

            # Extract JSON from response
            if text.startswith("["):
                cards = json.loads(text)
            else:
                # Try to find JSON in the response
                start = text.find("[")
                end = text.rfind("]") + 1
                if start >= 0 and end > start:
                    cards = json.loads(text[start:end])
                else:
                    cards = []

            if cards:
                await self._on_cards(cards)

        except Exception as e:
            print(f"Coaching analysis error: {e}")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def get_transcript(self) -> list[dict]:
        return [
            {"speaker": s.speaker, "text": s.text, "timestamp": s.timestamp}
            for s in self._transcript
        ]
