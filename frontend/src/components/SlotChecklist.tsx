import './SlotChecklist.css'

interface Slot {
  name: string
  status: string
  value?: any
  required?: boolean
}

interface SlotChecklistProps {
  phase: string
  slots: Slot[]
}

function SlotChecklist({ phase, slots }: SlotChecklistProps) {
  if (!slots || slots.length === 0) {
    return null
  }

  return (
    <div className="slot-checklist">
      <h3>確認項目</h3>
      <div className="slot-list">
        {slots.map((slot) => (
          <div key={slot.name} className={`slot-item ${slot.status}`}>
            <div className="slot-checkbox">
              {slot.status === 'filled' ? '☑' : '☐'}
            </div>
            <div className="slot-content">
              <div className="slot-name">{slot.name}</div>
              {slot.value && (
                <div className="slot-value">{String(slot.value)}</div>
              )}
              {slot.required && slot.status === 'pending' && (
                <span className="slot-badge required">必須</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default SlotChecklist
