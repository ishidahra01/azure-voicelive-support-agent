import './PhaseBadge.css'

interface PhaseBadgeProps {
  currentPhase: string
}

const PHASES = ['intake', 'identity', 'interview', 'visit', 'closing']

const PHASE_LABELS: Record<string, string> = {
  intake: '受付',
  identity: '本人確認',
  interview: '問診',
  visit: '訪問手配',
  closing: 'クロージング'
}

function PhaseBadge({ currentPhase }: PhaseBadgeProps) {
  const currentIndex = PHASES.indexOf(currentPhase)

  return (
    <div className="phase-badge">
      <h3>フェーズ進捗</h3>
      <div className="phase-track">
        {PHASES.map((phase, index) => {
          const status =
            index < currentIndex
              ? 'completed'
              : index === currentIndex
              ? 'active'
              : 'pending'

          return (
            <div key={phase} className={`phase-item ${status}`}>
              <div className="phase-icon">
                {status === 'completed' ? '✓' : index + 1}
              </div>
              <div className="phase-label">{PHASE_LABELS[phase]}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default PhaseBadge
