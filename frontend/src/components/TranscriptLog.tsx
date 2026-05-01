import { useEffect, useRef } from 'react'
import './TranscriptLog.css'

interface Transcript {
  role: string
  text: string
  timestamp: Date
}

interface TranscriptLogProps {
  transcripts: Transcript[]
}

function TranscriptLog({ transcripts }: TranscriptLogProps) {
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [transcripts])

  return (
    <div className="transcript-log">
      <h3>会話ログ</h3>
      <div className="transcript-content" ref={logRef}>
        {transcripts.length === 0 ? (
          <div className="empty-state">会話が開始されるとここに表示されます</div>
        ) : (
          transcripts.map((transcript, index) => (
            <div key={index} className={`transcript-item ${transcript.role}`}>
              <div className="transcript-meta">
                <span className="transcript-role">
                  {transcript.role === 'user' ? 'お客様' : 'エージェント'}
                </span>
                <span className="transcript-time">
                  {transcript.timestamp.toLocaleTimeString('ja-JP')}
                </span>
              </div>
              <div className="transcript-text">{transcript.text}</div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default TranscriptLog
