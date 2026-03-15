"""Abstract STT provider interface — designed for easy swap to Parakeet later."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class TranscriptSegment:
    text: str
    speaker: str  # "You" or "Interviewer"
    timestamp: float  # seconds from start
    is_final: bool = True


class STTProvider(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Initialize the STT engine."""

    @abstractmethod
    async def feed_audio(self, audio_chunk: bytes) -> None:
        """Feed raw PCM audio bytes to the engine."""

    @abstractmethod
    async def get_segments(self) -> AsyncIterator[TranscriptSegment]:
        """Yield transcript segments as they become available."""

    @abstractmethod
    async def stop(self) -> None:
        """Clean up resources."""
