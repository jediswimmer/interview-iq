# InterviewIQ 🎯

Real-time interview coaching overlay powered by Claude AI. Listens to both speakers, transcribes live with speaker identification, and displays coaching cards with recommended talking points, warnings, and strategy suggestions.

## Features

- **Live Transcription** — Real-time STT via Deepgram (streaming) or faster-whisper (local)
- **AI Coaching Cards** — Claude analyzes conversation every ~12s and suggests talking points, warnings, metrics, bridges, and strategies
- **RAG Knowledge Base** — Drop PDFs, DOCX, TXT, and MD files in `knowledge/` — the coaching engine automatically references them during analysis
- **Research Agent** — Separate Claude agent identifies PE/VC terms, Microsoft jargon, company names, and industry terminology in real-time, showing definition cards with a 60s TTL
- **WebSocket-Driven** — All updates stream live to the React frontend

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

## Knowledge Base

Drop research documents into the `knowledge/` directory. Supported formats: PDF, DOCX, TXT, MD.

The coaching engine embeds documents with `all-MiniLM-L6-v2` into a FAISS index and searches for relevant context before each coaching analysis.

**API endpoints:**
- `GET /api/knowledge/status` — doc count, file list, last indexed
- `POST /api/knowledge/reload` — re-index all documents

## STT Providers

| Provider | When Used | Latency |
|----------|-----------|---------|
| Deepgram | `DEEPGRAM_API_KEY` set in `.env` | ~300ms (best) |
| faster-whisper | No Deepgram key (default) | ~2-3s |

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
                        ┌─────────────────────┼─────────────────────┐
                        │               │               │           │
                  ┌─────┴─────┐  ┌─────┴─────┐  ┌─────┴─────┐  ┌──┴────────┐
                  │  Audio    │  │  STT      │  │  Claude   │  │  Research │
                  │  Capture  │  │  Engine   │  │  Coach    │  │  Agent    │
                  │  (PyAudio)│  │  (Whisper)│  │  + RAG KB │  │  (Claude) │
                  └───────────┘  └───────────┘  └───────────┘  └───────────┘
```
