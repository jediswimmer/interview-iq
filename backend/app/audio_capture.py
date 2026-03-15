"""System audio capture using PyAudio — captures microphone input."""

import asyncio
import pyaudio
from .config import SAMPLE_RATE, CHANNELS, CHUNK_DURATION_MS


class AudioCapture:
    def __init__(self):
        self._pa = None
        self._stream = None
        self._running = False
        self._chunk_size = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)

    def list_devices(self) -> list[dict]:
        pa = pyaudio.PyAudio()
        devices = []
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info["maxInputChannels"] > 0:
                devices.append({
                    "index": i,
                    "name": info["name"],
                    "channels": info["maxInputChannels"],
                    "sample_rate": int(info["defaultSampleRate"]),
                })
        pa.terminate()
        return devices

    async def start(self, device_index: int | None = None, on_audio: callable = None):
        self._pa = pyaudio.PyAudio()
        self._running = True

        kwargs = {
            "format": pyaudio.paInt16,
            "channels": CHANNELS,
            "rate": SAMPLE_RATE,
            "input": True,
            "frames_per_buffer": self._chunk_size,
        }
        if device_index is not None:
            kwargs["input_device_index"] = device_index

        self._stream = self._pa.open(**kwargs)

        # Read audio in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        while self._running:
            data = await loop.run_in_executor(
                None, self._stream.read, self._chunk_size, False
            )
            if on_audio:
                await on_audio(data)

    def stop(self):
        self._running = False
        if self._stream:
            self._stream.stop_stream()
            self._stream.close()
        if self._pa:
            self._pa.terminate()
