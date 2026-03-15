# InterviewIQ 🎯

Real-time interview coaching overlay powered by Claude AI. Listens to both speakers, transcribes live with speaker identification, and displays coaching cards with recommended talking points, warnings, and strategy suggestions.

## Quick Start

```bash
# 1. Set up your API key
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# 2. Run everything
./start.sh
```

Opens at **http://localhost:3000**

## Manual Setup

### Backend (Python)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (React/Vite)

```bash
cd frontend
npm install
npm run dev
```

## STT Providers

| Provider | When Used | Latency |
|----------|-----------|---------|
| Deepgram | `DEEPGRAM_API_KEY` set in `.env` | ~300ms (best) |
| faster-whisper | No Deepgram key (default) | ~2-3s |
| Parakeet (NVIDIA) | Future — abstraction ready | TBD |

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Space` | Pause / Resume |
| `Esc` | Hide overlay |

## Architecture

```
┌─────────────────┐     WebSocket      ┌──────────────┐
│  React Frontend │◄──────────────────►│  FastAPI      │
│  (Vite, :3000)  │                    │  (:8000)      │
└─────────────────┘                    └──────┬───────┘
                                              │
                              ┌───────────────┼───────────────┐
                              │               │               │
                        ┌─────┴─────┐  ┌─────┴─────┐  ┌─────┴─────┐
                        │  Audio    │  │  STT      │  │  Claude   │
                        │  Capture  │  │  Engine   │  │  Coach    │
                        │  (PyAudio)│  │  (Whisper)│  │  (API)    │
                        └───────────┘  └───────────┘  └───────────┘
```
