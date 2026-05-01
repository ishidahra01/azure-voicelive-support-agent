import './HandoffIndicator.css'

interface HandoffIndicatorProps {
  status: string
  targetDesk: string
}

const STATUS_LABELS: Record<string, string> = {
  initiating: '転送準備中...',
  connecting: '接続中...',
  connected: '転送完了',
  failed: '転送失敗'
}

function HandoffIndicator({ status, targetDesk }: HandoffIndicatorProps) {
  if (!status) {
    return null
  }

  return (
    <div className={`handoff-indicator ${status}`}>
      <div className="handoff-icon">
        {status === 'connected' ? '✓' : '⟳'}
      </div>
      <div className="handoff-content">
        <div className="handoff-status">{STATUS_LABELS[status] || status}</div>
        {targetDesk && (
          <div className="handoff-desk">
            {targetDesk === 'fault' ? '故障窓口' : targetDesk}
          </div>
        )}
      </div>
    </div>
  )
}

export default HandoffIndicator
