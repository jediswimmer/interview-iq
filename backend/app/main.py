"""InterviewIQ — Real-time interview coaching server."""

import asyncio
import json
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import STT_PROVIDER
from .audio_capture import AudioCapture
from .coach import CoachingEngine

app = FastAPI(title="InterviewIQ")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
audio_capture = AudioCapture()
stt_provider = None
coaching_engine = None
connected_clients: set[WebSocket] = set()
session_start_time: float = 0
session_paused: bool = False


async def broadcast(msg: dict):
    """Send a message to all connected WebSocket clients."""
    data = json.dumps(msg)
    disconnected = set()
    for ws in connected_clients:
        try:
            await ws.send_text(data)
        except Exception:
            disconnected.add(ws)
    connected_clients -= disconnected


async def on_coaching_cards(cards: list[dict]):
    """Called by coaching engine when new cards are generated."""
    await broadcast({"type": "coaching", "cards": cards, "timestamp": time.time() - session_start_time})


@app.get("/api/devices")
async def list_devices():
    return audio_capture.list_devices()


@app.get("/api/status")
async def status():
    return {
        "running": stt_provider is not None,
        "paused": session_paused,
        "stt_provider": STT_PROVIDER,
        "elapsed": time.time() - session_start_time if session_start_time else 0,
    }


@app.post("/api/start")
async def start_session(device_index: int | None = None):
    global stt_provider, coaching_engine, session_start_time, session_paused

    if stt_provider is not None:
        return {"error": "Session already running"}

    # Initialize STT
    if STT_PROVIDER == "deepgram":
        from .stt_deepgram import DeepgramSTTProvider
        stt_provider = DeepgramSTTProvider()
    else:
        from .stt_whisper import WhisperSTTProvider
        stt_provider = WhisperSTTProvider()

    await stt_provider.start()

    # Initialize coaching engine
    coaching_engine = CoachingEngine(on_cards=on_coaching_cards)
    await coaching_engine.start()

    session_start_time = time.time()
    session_paused = False

    # Start audio capture in background
    asyncio.create_task(_audio_loop(device_index))
    # Start transcript polling
    asyncio.create_task(_transcript_poll_loop())

    return {"status": "started", "stt_provider": STT_PROVIDER}


@app.post("/api/stop")
async def stop_session():
    global stt_provider, coaching_engine, session_start_time
    if stt_provider:
        await stt_provider.stop()
        stt_provider = None
    if coaching_engine:
        await coaching_engine.stop()
        coaching_engine = None
    audio_capture.stop()
    session_start_time = 0
    return {"status": "stopped"}


@app.post("/api/pause")
async def pause_session():
    global session_paused
    session_paused = not session_paused
    await broadcast({"type": "status", "paused": session_paused})
    return {"paused": session_paused}


@app.get("/api/transcript")
async def get_transcript():
    if coaching_engine:
        return coaching_engine.get_transcript()
    return []


async def _audio_loop(device_index: int | None):
    """Capture audio and feed to STT."""
    async def on_audio(chunk: bytes):
        if not session_paused and stt_provider:
            await stt_provider.feed_audio(chunk)

    try:
        await audio_capture.start(device_index=device_index, on_audio=on_audio)
    except Exception as e:
        print(f"Audio capture error: {e}")
        await broadcast({"type": "error", "message": f"Audio capture error: {e}"})


async def _transcript_poll_loop():
    """Poll STT for new segments and broadcast."""
    while stt_provider:
        try:
            async for segment in stt_provider.get_segments():
                # Send to coaching engine
                if coaching_engine:
                    await coaching_engine.add_segment(segment)

                # Broadcast to connected clients
                await broadcast({
                    "type": "transcript",
                    "speaker": segment.speaker,
                    "text": segment.text,
                    "timestamp": segment.timestamp,
                    "is_final": segment.is_final,
                })
        except Exception:
            pass
        await asyncio.sleep(0.3)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.add(ws)

    # Send current state
    await ws.send_text(json.dumps({
        "type": "init",
        "stt_provider": STT_PROVIDER,
        "running": stt_provider is not None,
        "paused": session_paused,
        "elapsed": time.time() - session_start_time if session_start_time else 0,
        "transcript": coaching_engine.get_transcript() if coaching_engine else [],
    }))

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg.get("action") == "start":
                await start_session(msg.get("device_index"))
            elif msg.get("action") == "stop":
                await stop_session()
            elif msg.get("action") == "pause":
                await pause_session()

    except WebSocketDisconnect:
        connected_clients.discard(ws)
