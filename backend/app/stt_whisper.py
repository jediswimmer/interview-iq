"""Faster-whisper STT provider for Apple Silicon (Metal acceleration)."""

import asyncio
import time
import numpy as np
from typing import AsyncIterator
from .stt_base import STTProvider, TranscriptSegment
from .config import SAMPLE_RATE

# Minimum audio length before processing (seconds)
MIN_AUDIO_SEC = 2.0
# Maximum buffer before forced processing
MAX_AUDIO_SEC = 15.0


class WhisperSTTProvider(STTProvider):
    def __init__(self):
        self._model = None
        self._audio_buffer = bytearray()
        self._segments_queue: asyncio.Queue[TranscriptSegment] = asyncio.Queue()
        self._start_time = 0.0
        self._last_process_time = 0.0
        self._running = False
        self._process_task = None
        self._last_speaker = "Interviewer"  # simple alternation heuristic

    async def start(self) -> None:
        from faster_whisper import WhisperModel
        # Use small model for speed — good enough for coaching
        self._model = WhisperModel(
            "small",
            device="cpu",  # faster-whisper uses CPU but is still fast on M-series
            compute_type="int8",
        )
        self._start_time = time.time()
        self._last_process_time = self._start_time
        self._running = True
        self._process_task = asyncio.create_task(self._process_loop())

    async def feed_audio(self, audio_chunk: bytes) -> None:
        self._audio_buffer.extend(audio_chunk)

    async def _process_loop(self):
        """Background loop that processes accumulated audio."""
        while self._running:
            await asyncio.sleep(0.5)
            buffer_sec = len(self._audio_buffer) / (SAMPLE_RATE * 2)  # 16-bit = 2 bytes/sample

            if buffer_sec < MIN_AUDIO_SEC:
                continue

            if buffer_sec >= MIN_AUDIO_SEC or buffer_sec >= MAX_AUDIO_SEC:
                await self._process_buffer()

    async def _process_buffer(self):
        if not self._audio_buffer or not self._model:
            return

        raw = bytes(self._audio_buffer)
        self._audio_buffer.clear()

        # Convert to float32 numpy array
        audio_np = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        # Run transcription in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        segments_gen, info = await loop.run_in_executor(
            None,
            lambda: self._model.transcribe(
                audio_np,
                language="en",
                beam_size=3,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
            )
        )

        segments_list = await loop.run_in_executor(None, list, segments_gen)

        now = time.time()
        for seg in segments_list:
            text = seg.text.strip()
            if not text:
                continue

            # Simple speaker diarization heuristic:
            # Questions → interviewer, statements → candidate
            # Also alternate on pauses
            speaker = self._guess_speaker(text)

            await self._segments_queue.put(TranscriptSegment(
                text=text,
                speaker=speaker,
                timestamp=now - self._start_time,
                is_final=True,
            ))

        self._last_process_time = now

    def _guess_speaker(self, text: str) -> str:
        """Simple heuristic for speaker identification.

        In a real setup, you'd use embedding-based diarization.
        For now: questions are likely the interviewer, statements are Scott.
        """
        text_lower = text.lower().strip()
        # Questions are likely from interviewer
        if text_lower.endswith('?'):
            self._last_speaker = "Interviewer"
        # Short acknowledgments could be either
        elif len(text_lower.split()) <= 3:
            pass  # keep last speaker
        else:
            # Longer statements — alternate from last
            if self._last_speaker == "Interviewer":
                self._last_speaker = "You"
            else:
                self._last_speaker = "Interviewer"

        return self._last_speaker

    async def get_segments(self) -> AsyncIterator[TranscriptSegment]:
        while True:
            try:
                segment = self._segments_queue.get_nowait()
                yield segment
            except asyncio.QueueEmpty:
                return

    async def stop(self) -> None:
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        self._model = None
