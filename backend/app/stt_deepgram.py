"""Deepgram streaming STT provider — lowest latency option."""

import asyncio
import json
import time
from typing import AsyncIterator

try:
    import websockets
except ImportError:
    websockets = None

from .stt_base import STTProvider, TranscriptSegment
from .config import DEEPGRAM_API_KEY, SAMPLE_RATE


class DeepgramSTTProvider(STTProvider):
    def __init__(self):
        self._ws = None
        self._segments_queue: asyncio.Queue[TranscriptSegment] = asyncio.Queue()
        self._start_time = 0.0
        self._running = False
        self._receive_task = None

    async def start(self) -> None:
        url = (
            "wss://api.deepgram.com/v1/listen"
            f"?encoding=linear16&sample_rate={SAMPLE_RATE}&channels=1"
            "&model=nova-2&smart_format=true&diarize=true&punctuate=true"
        )
        self._ws = await websockets.connect(
            url,
            additional_headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"},
        )
        self._start_time = time.time()
        self._running = True
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def feed_audio(self, audio_chunk: bytes) -> None:
        if self._ws:
            await self._ws.send(audio_chunk)

    async def _receive_loop(self):
        try:
            async for msg in self._ws:
                data = json.loads(msg)
                if data.get("type") != "Results":
                    continue

                channel = data.get("channel", {})
                alt = channel.get("alternatives", [{}])[0]
                transcript = alt.get("transcript", "").strip()
                if not transcript:
                    continue

                is_final = data.get("is_final", False)
                if not is_final:
                    continue

                # Use Deepgram's diarization
                words = alt.get("words", [])
                speaker_id = words[0].get("speaker", 0) if words else 0
                speaker = "You" if speaker_id == 0 else "Interviewer"

                await self._segments_queue.put(TranscriptSegment(
                    text=transcript,
                    speaker=speaker,
                    timestamp=time.time() - self._start_time,
                    is_final=True,
                ))
        except Exception:
            pass  # Connection closed

    async def get_segments(self) -> AsyncIterator[TranscriptSegment]:
        while True:
            try:
                segment = self._segments_queue.get_nowait()
                yield segment
            except asyncio.QueueEmpty:
                return

    async def stop(self) -> None:
        self._running = False
        if self._receive_task:
            self._receive_task.cancel()
        if self._ws:
            await self._ws.close()
