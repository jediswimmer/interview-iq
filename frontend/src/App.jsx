import { useState, useEffect, useRef, useCallback } from 'react'
import './App.css'

const WS_URL = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`
const API_URL = '/api'

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

const CARD_COLORS = {
  TALKING_POINT: { border: '#38bdf8', bg: 'rgba(56, 189, 248, 0.08)', icon: '💬' },
  WARNING: { border: '#f87171', bg: 'rgba(248, 113, 113, 0.08)', icon: '⚠️' },
  STRATEGY: { border: '#a78bfa', bg: 'rgba(167, 139, 250, 0.08)', icon: '🎯' },
  METRIC: { border: '#34d399', bg: 'rgba(52, 211, 153, 0.08)', icon: '📊' },
  BRIDGE: { border: '#fbbf24', bg: 'rgba(251, 191, 36, 0.08)', icon: '🌉' },
  REFERENCE: { border: '#f59e0b', bg: 'rgba(245, 158, 11, 0.08)', icon: '📚' },
}

function App() {
  const [connected, setConnected] = useState(false)
  const [running, setRunning] = useState(false)
  const [paused, setPaused] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [transcript, setTranscript] = useState([])
  const [coachingCards, setCoachingCards] = useState([])
  const [devices, setDevices] = useState([])
  const [selectedDevice, setSelectedDevice] = useState(null)
  const [sttProvider, setSttProvider] = useState('')
  const [error, setError] = useState(null)
  const [researchCards, setResearchCards] = useState([])
  const [kbStatus, setKbStatus] = useState({ doc_count: 0, files: [] })
  const [kbOpen, setKbOpen] = useState(false)
  const [kbReloading, setKbReloading] = useState(false)

  const wsRef = useRef(null)
  const transcriptEndRef = useRef(null)
  const timerRef = useRef(null)
  const cardIdRef = useRef(0)

  // Auto-scroll transcript
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript])

  // Timer
  useEffect(() => {
    if (running && !paused) {
      timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    } else {
      clearInterval(timerRef.current)
    }
    return () => clearInterval(timerRef.current)
  }, [running, paused])

  // Auto-expire coaching cards after 30s, research cards after 60s
  useEffect(() => {
    const interval = setInterval(() => {
      const now = Date.now()
      setCoachingCards(cards => cards.filter(c => now - c._addedAt < 30000))
      setResearchCards(cards => cards.filter(c => now - c._addedAt < 60000))
    }, 2000)
    return () => clearInterval(interval)
  }, [])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      if (e.code === 'Space' && !e.target.closest('input, select, button')) {
        e.preventDefault()
        if (running) togglePause()
      }
      if (e.code === 'Escape') {
        // Could hide overlay — for now, stop session
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [running])

  // Fetch devices and KB status on mount
  useEffect(() => {
    fetch(`${API_URL}/devices`)
      .then(r => r.json())
      .then(setDevices)
      .catch(() => {})
    fetch(`${API_URL}/knowledge/status`)
      .then(r => r.json())
      .then(setKbStatus)
      .catch(() => {})
  }, [])

  const reloadKb = () => {
    setKbReloading(true)
    fetch(`${API_URL}/knowledge/reload`, { method: 'POST' })
      .then(r => r.json())
      .then(s => { setKbStatus(s); setKbReloading(false) })
      .catch(() => setKbReloading(false))
  }

  // WebSocket connection
  const connectWs = useCallback(() => {
    const ws = new WebSocket(WS_URL)

    ws.onopen = () => {
      setConnected(true)
      setError(null)
    }

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)

      if (msg.type === 'init') {
        setRunning(msg.running)
        setPaused(msg.paused)
        setSttProvider(msg.stt_provider)
        if (msg.transcript?.length) setTranscript(msg.transcript)
        if (msg.elapsed) setElapsed(Math.floor(msg.elapsed))
      }

      if (msg.type === 'transcript') {
        setTranscript(prev => [...prev, {
          speaker: msg.speaker,
          text: msg.text,
          timestamp: msg.timestamp,
        }])
      }

      if (msg.type === 'coaching') {
        const newCards = msg.cards.map(card => ({
          ...card,
          _id: ++cardIdRef.current,
          _addedAt: Date.now(),
        }))
        setCoachingCards(prev => [...newCards, ...prev].slice(0, 4))
      }

      if (msg.type === 'research') {
        const newCards = msg.cards.map(card => ({
          ...card,
          _id: ++cardIdRef.current,
          _addedAt: Date.now(),
        }))
        setResearchCards(newCards.slice(0, 3))
      }

      if (msg.type === 'status') {
        setPaused(msg.paused)
      }

      if (msg.type === 'error') {
        setError(msg.message)
      }
    }

    ws.onclose = () => {
      setConnected(false)
      setTimeout(connectWs, 2000)
    }

    wsRef.current = ws
  }, [])

  useEffect(() => {
    connectWs()
    return () => wsRef.current?.close()
  }, [connectWs])

  const startSession = () => {
    wsRef.current?.send(JSON.stringify({
      action: 'start',
      device_index: selectedDevice,
    }))
    setRunning(true)
    setElapsed(0)
    setTranscript([])
    setCoachingCards([])
    setResearchCards([])
  }

  const stopSession = () => {
    wsRef.current?.send(JSON.stringify({ action: 'stop' }))
    setRunning(false)
    setPaused(false)
  }

  const togglePause = () => {
    wsRef.current?.send(JSON.stringify({ action: 'pause' }))
  }

  return (
    <div className="app">
      {/* Top Bar */}
      <header className="top-bar">
        <div className="top-bar-left">
          <div className="logo">
            <span className="logo-icon">🎯</span>
            <span className="logo-text">InterviewIQ</span>
          </div>
          <div className="interview-info">
            VP Partnerships — Monday 4:30 PM
          </div>
          <div className="kb-indicator" onClick={() => setKbOpen(!kbOpen)}>
            <span>📚 {kbStatus.doc_count} docs</span>
            {kbOpen && (
              <div className="kb-popover">
                <div className="kb-popover-header">
                  <strong>Knowledge Base</strong>
                  <button className="btn btn-kb-reload" onClick={e => { e.stopPropagation(); reloadKb() }} disabled={kbReloading}>
                    {kbReloading ? '...' : 'Reload'}
                  </button>
                </div>
                {kbStatus.files?.length > 0 ? (
                  <ul className="kb-file-list">
                    {kbStatus.files.map(f => <li key={f}>{f}</li>)}
                  </ul>
                ) : (
                  <p className="kb-empty">No documents indexed</p>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="top-bar-center">
          <div className={`timer ${running ? (paused ? 'paused' : 'active') : ''}`}>
            <div className={`status-dot ${running ? (paused ? 'paused' : 'live') : 'idle'}`} />
            <span className="timer-value">{formatTime(elapsed)}</span>
            {running && <span className="timer-label">{paused ? 'PAUSED' : 'LIVE'}</span>}
          </div>
        </div>

        <div className="top-bar-right">
          <div className={`connection-badge ${connected ? 'connected' : 'disconnected'}`}>
            <span className="connection-dot" />
            {connected ? sttProvider || 'Connected' : 'Disconnected'}
          </div>

          {!running ? (
            <button className="btn btn-start" onClick={startSession} disabled={!connected}>
              Start Session
            </button>
          ) : (
            <>
              <button className="btn btn-pause" onClick={togglePause}>
                {paused ? '▶ Resume' : '⏸ Pause'}
              </button>
              <button className="btn btn-stop" onClick={stopSession}>
                Stop
              </button>
            </>
          )}
        </div>
      </header>

      {error && (
        <div className="error-banner">
          {error}
          <button onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Main Content */}
      <main className="main-content">
        {/* Transcript Panel */}
        <section className="transcript-panel">
          <div className="panel-header">
            <h2>Live Transcript</h2>
            <span className="segment-count">{transcript.length} segments</span>
          </div>

          <div className="transcript-scroll">
            {transcript.length === 0 && (
              <div className="empty-state">
                <div className="empty-icon">🎤</div>
                <p>{running ? 'Listening...' : 'Start a session to begin transcribing'}</p>
                {!running && devices.length > 0 && (
                  <div className="device-select">
                    <label>Microphone:</label>
                    <select
                      value={selectedDevice ?? ''}
                      onChange={e => setSelectedDevice(e.target.value ? Number(e.target.value) : null)}
                    >
                      <option value="">System Default</option>
                      {devices.map(d => (
                        <option key={d.index} value={d.index}>{d.name}</option>
                      ))}
                    </select>
                  </div>
                )}
                <div className="shortcuts-hint">
                  <kbd>Space</kbd> Pause/Resume &nbsp; <kbd>Esc</kbd> Hide
                </div>
              </div>
            )}

            {transcript.map((seg, i) => (
              <div key={i} className={`transcript-entry ${seg.speaker === 'You' ? 'speaker-you' : 'speaker-them'}`}>
                <div className="speaker-label">
                  <span className={`speaker-badge ${seg.speaker === 'You' ? 'you' : 'them'}`}>
                    {seg.speaker}
                  </span>
                  <span className="timestamp">{formatTime(seg.timestamp)}</span>
                </div>
                <p className="transcript-text">{seg.text}</p>
              </div>
            ))}
            <div ref={transcriptEndRef} />
          </div>
        </section>

        {/* Coaching Panel */}
        <section className="coaching-panel">
          <div className="panel-header">
            <h2>Coaching</h2>
            <span className="coaching-badge">AI-Powered</span>
          </div>

          <div className="coaching-scroll">
            {coachingCards.length === 0 && (
              <div className="empty-state">
                <div className="empty-icon">🧠</div>
                <p>{running ? 'Analyzing conversation...' : 'Coaching cards will appear here during the interview'}</p>
              </div>
            )}

            {coachingCards.map(card => {
              const style = CARD_COLORS[card.type] || CARD_COLORS.TALKING_POINT
              return (
                <div
                  key={card._id}
                  className="coaching-card"
                  style={{
                    borderLeftColor: style.border,
                    background: style.bg,
                  }}
                >
                  <div className="card-header">
                    <span className="card-icon">{style.icon}</span>
                    <span className="card-type" style={{ color: style.border }}>{card.type}</span>
                  </div>
                  <h3 className="card-title">{card.title}</h3>
                  <p className="card-body">{card.body}</p>
                </div>
              )
            })}
          </div>
        </section>

        {/* Research Panel */}
        <section className="research-panel">
          <div className="panel-header">
            <h2>Research</h2>
            {researchCards.length > 0 && (
              <span className="research-badge">{researchCards.length}</span>
            )}
          </div>

          <div className="research-scroll">
            {researchCards.length === 0 && (
              <div className="empty-state">
                <div className="empty-icon">🔬</div>
                <p>{running ? 'Scanning for terms...' : 'Term definitions will appear here'}</p>
              </div>
            )}

            {researchCards.map(card => (
              <div key={card._id} className="research-card">
                <h3 className="research-term">{card.term}</h3>
                <p className="research-definition">{card.definition}</p>
                <p className="research-relevance">{card.relevance}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
