import { useState, useEffect, useRef } from 'react'
import './App.css'
import PhaseBadge from './components/PhaseBadge'
import SlotChecklist from './components/SlotChecklist'
import HandoffIndicator from './components/HandoffIndicator'
import TranscriptLog from './components/TranscriptLog'

const WEBSOCKET_URL = 'ws://localhost:8000/ws/voice'

interface Message {
  type: string
  role?: string
  text?: string
  phase?: string
  slots?: Array<{
    name: string
    status: string
    value?: any
    required?: boolean
  }>
  status?: string
  target_desk?: string
  message?: string
}

interface Transcript {
  role: string
  text: string
  timestamp: Date
}

function App() {
  const [connected, setConnected] = useState(false)
  const [currentPhase, setCurrentPhase] = useState<string>('')
  const [slots, setSlots] = useState<any[]>([])
  const [handoffStatus, setHandoffStatus] = useState<string>('')
  const [handoffDesk, setHandoffDesk] = useState<string>('')
  const [transcripts, setTranscripts] = useState<Transcript[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  const connect = () => {
    const ws = new WebSocket(WEBSOCKET_URL)

    ws.onopen = () => {
      console.log('WebSocket connected')
      setConnected(true)
    }

    ws.onmessage = (event) => {
      try {
        const message: Message = JSON.parse(event.data)
        console.log('Received message:', message)

        switch (message.type) {
          case 'transcript':
            if (message.role && message.text) {
              setTranscripts(prev => [...prev, {
                role: message.role,
                text: message.text!,
                timestamp: new Date()
              }])
            }
            break

          case 'phase_changed':
            if (message.phase) {
              setCurrentPhase(message.phase)
            }
            break

          case 'slots_snapshot':
            if (message.phase && message.slots) {
              setCurrentPhase(message.phase)
              setSlots(message.slots)
            }
            break

          case 'handoff_status':
            if (message.status) {
              setHandoffStatus(message.status)
              if (message.target_desk) {
                setHandoffDesk(message.target_desk)
              }
            }
            break

          case 'session_end':
            console.log('Session ended:', message.message)
            setConnected(false)
            break
        }
      } catch (error) {
        console.error('Error parsing message:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
      setConnected(false)
    }

    wsRef.current = ws
  }

  const disconnect = () => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }

  const sendDemoRouteFault = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'demo_route_fault',
        summary: 'インターネットが繋がらない',
        caller_attrs: { phone: '03-1234-5678' }
      }))
    }
  }

  useEffect(() => {
    return () => {
      disconnect()
    }
  }, [])

  return (
    <div className="app">
      <header className="header">
        <h1>🎙️ Azure Voice Live Support Agent</h1>
        <div className="connection-status">
          <span className={`status-dot ${connected ? 'connected' : 'disconnected'}`}></span>
          {connected ? '接続中' : '未接続'}
        </div>
      </header>

      <div className="main-content">
        <div className="left-panel">
          <div className="control-panel">
            <h2>接続制御</h2>
            <div className="button-group">
              <button onClick={connect} disabled={connected}>
                接続
              </button>
              <button onClick={disconnect} disabled={!connected}>
                切断
              </button>
            </div>

            <div className="demo-controls">
              <h3>デモ操作</h3>
              <button onClick={sendDemoRouteFault} disabled={!connected}>
                故障窓口に転送（デモ）
              </button>
            </div>
          </div>

          <HandoffIndicator status={handoffStatus} targetDesk={handoffDesk} />

          {currentPhase && (
            <>
              <PhaseBadge currentPhase={currentPhase} />
              <SlotChecklist phase={currentPhase} slots={slots} />
            </>
          )}
        </div>

        <div className="right-panel">
          <TranscriptLog transcripts={transcripts} />
        </div>
      </div>
    </div>
  )
}

export default App
