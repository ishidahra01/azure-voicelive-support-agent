import { useState, useEffect, useRef } from 'react'
import './App.css'
import PhaseBadge from './components/PhaseBadge'
import SlotChecklist from './components/SlotChecklist'
import HandoffIndicator from './components/HandoffIndicator'
import TranscriptLog from './components/TranscriptLog'

const WEBSOCKET_URL = 'ws://localhost:8000/ws/voice'

interface Message {
  type: string
  audio?: string
  role?: string
  text?: string
  phase?: string
  to?: string
  from?: string | null
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
  const audioContextRef = useRef<AudioContext | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const mediaSourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const nextPlaybackTimeRef = useRef(0)
  const playbackSourcesRef = useRef<AudioBufferSourceNode[]>([])

  const ensureAudioContext = () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext()
    }
    return audioContextRef.current
  }

  const base64ToArrayBuffer = (base64: string) => {
    const binary = atob(base64)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i += 1) {
      bytes[i] = binary.charCodeAt(i)
    }
    return bytes.buffer
  }

  const arrayBufferToBase64 = (buffer: ArrayBuffer) => {
    const bytes = new Uint8Array(buffer)
    let binary = ''
    for (let i = 0; i < bytes.byteLength; i += 1) {
      binary += String.fromCharCode(bytes[i])
    }
    return btoa(binary)
  }

  const downsampleToPcm16 = (input: Float32Array, inputSampleRate: number) => {
    const outputSampleRate = 24000
    const ratio = inputSampleRate / outputSampleRate
    const outputLength = Math.floor(input.length / ratio)
    const output = new ArrayBuffer(outputLength * 2)
    const view = new DataView(output)

    for (let i = 0; i < outputLength; i += 1) {
      const sampleIndex = Math.floor(i * ratio)
      const sample = Math.max(-1, Math.min(1, input[sampleIndex]))
      view.setInt16(i * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
    }

    return output
  }

  const stopPlayback = () => {
    playbackSourcesRef.current.forEach(source => {
      try {
        source.stop()
      } catch {
        // Source may already have ended.
      }
    })
    playbackSourcesRef.current = []
    nextPlaybackTimeRef.current = audioContextRef.current?.currentTime ?? 0
  }

  const playPcm16Audio = async (audioBase64: string) => {
    const audioContext = ensureAudioContext()
    if (audioContext.state === 'suspended') {
      await audioContext.resume()
    }

    const buffer = base64ToArrayBuffer(audioBase64)
    const pcm = new Int16Array(buffer)
    const audioBuffer = audioContext.createBuffer(1, pcm.length, 24000)
    const channel = audioBuffer.getChannelData(0)

    for (let i = 0; i < pcm.length; i += 1) {
      channel[i] = pcm[i] / 0x8000
    }

    const source = audioContext.createBufferSource()
    source.buffer = audioBuffer
    source.connect(audioContext.destination)

    const startAt = Math.max(audioContext.currentTime, nextPlaybackTimeRef.current)
    source.start(startAt)
    nextPlaybackTimeRef.current = startAt + audioBuffer.duration
    playbackSourcesRef.current.push(source)
    source.onended = () => {
      playbackSourcesRef.current = playbackSourcesRef.current.filter(item => item !== source)
    }
  }

  const startMicrophone = async (ws: WebSocket) => {
    const audioContext = ensureAudioContext()
    if (audioContext.state === 'suspended') {
      await audioContext.resume()
    }

    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    })

    const source = audioContext.createMediaStreamSource(stream)
    const processor = audioContext.createScriptProcessor(4096, 1, 1)

    processor.onaudioprocess = (event) => {
      if (ws.readyState !== WebSocket.OPEN) {
        return
      }

      const input = event.inputBuffer.getChannelData(0)
      const pcm16 = downsampleToPcm16(input, audioContext.sampleRate)
      ws.send(JSON.stringify({
        type: 'audio',
        audio: arrayBufferToBase64(pcm16),
      }))
    }

    source.connect(processor)
    processor.connect(audioContext.destination)

    mediaStreamRef.current = stream
    mediaSourceRef.current = source
    processorRef.current = processor
  }

  const stopMicrophone = () => {
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current.onaudioprocess = null
      processorRef.current = null
    }

    if (mediaSourceRef.current) {
      mediaSourceRef.current.disconnect()
      mediaSourceRef.current = null
    }

    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop())
      mediaStreamRef.current = null
    }
  }

  const connect = () => {
    const ws = new WebSocket(WEBSOCKET_URL)

    ws.onopen = async () => {
      console.log('WebSocket connected')
      try {
        await startMicrophone(ws)
        setConnected(true)
      } catch (error) {
        console.error('Microphone startup failed:', error)
        ws.close()
      }
    }

    ws.onmessage = (event) => {
      try {
        const message: Message = JSON.parse(event.data)
        console.log('Received message:', message)

        switch (message.type) {
          case 'audio':
            if (message.audio) {
              playPcm16Audio(message.audio)
            }
            break

          case 'speech_started':
            stopPlayback()
            break

          case 'transcript':
            if (message.role && message.text) {
              const role = message.role
              const text = message.text
              setTranscripts(prev => [...prev, {
                role,
                text,
                timestamp: new Date()
              }])
            }
            break

          case 'phase_changed':
            if (message.to || message.phase) {
              setCurrentPhase(message.to ?? message.phase ?? '')
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
      stopMicrophone()
      stopPlayback()
      setConnected(false)
    }

    wsRef.current = ws
  }

  const disconnect = () => {
    if (wsRef.current) {
      wsRef.current.send(JSON.stringify({ type: 'control', action: 'end' }))
      wsRef.current.close()
      wsRef.current = null
    }
    stopMicrophone()
    stopPlayback()
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
