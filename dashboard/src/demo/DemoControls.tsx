interface Props {
  currentStep: number
  totalSteps: number
  paused: boolean
  muted: boolean
  title: string
  onPrev: () => void
  onNext: () => void
  onTogglePause: () => void
  onToggleMute: () => void
  onExit: () => void
}

const btn: React.CSSProperties = {
  background: 'rgba(255,255,255,0.1)',
  border: '1px solid rgba(255,255,255,0.15)',
  color: 'white', borderRadius: 8,
  padding: '8px 14px', fontSize: 16,
  cursor: 'pointer', minWidth: 44,
  fontFamily: 'inherit',
}

export default function DemoControls({
  currentStep, totalSteps, paused, muted, title,
  onPrev, onNext, onTogglePause, onToggleMute, onExit,
}: Props) {
  const progress = ((currentStep + 1) / totalSteps) * 100
  return (
    <div style={{
      position: 'fixed', bottom: 0, left: 0, right: 0,
      background: 'rgba(15, 39, 68, 0.97)',
      backdropFilter: 'blur(8px)',
      padding: '12px 20px',
      display: 'flex', alignItems: 'center', gap: 14,
      zIndex: 9001,
      borderTop: '1px solid rgba(160, 120, 48, 0.3)',
      fontFamily: 'Inter, system-ui, sans-serif',
    }}>
      <button onClick={onPrev} disabled={currentStep === 0}
              style={{ ...btn, opacity: currentStep === 0 ? 0.35 : 1 }}>⏮</button>
      <button onClick={onTogglePause} style={btn}>{paused ? '▶' : '⏸'}</button>
      <button onClick={onNext} style={{ ...btn, background: '#A07830', color: '#1A3A5C', borderColor: '#A07830' }}>⏭</button>

      <div style={{ flex: 1, minWidth: 0, margin: '0 6px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', color: '#A07830', fontSize: 11, fontWeight: 700, marginBottom: 4 }}>
          <span style={{ fontFamily: 'Georgia, serif' }}>Step {currentStep + 1} of {totalSteps} · {title}</span>
          <span style={{ color: '#9CA3AF', fontWeight: 400 }}>{Math.round(progress)}%</span>
        </div>
        <div style={{ height: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${progress}%`, background: '#A07830', transition: 'width 0.3s ease' }} />
        </div>
        <div style={{ display: 'flex', gap: 3, marginTop: 4, justifyContent: 'center' }}>
          {Array.from({ length: totalSteps }, (_, i) => (
            <div key={i} style={{ width: 6, height: 6, borderRadius: 3,
              background: i <= currentStep ? '#A07830' : 'rgba(255,255,255,0.18)' }} />
          ))}
        </div>
      </div>

      <button onClick={onToggleMute} style={btn} title={muted ? 'Unmute' : 'Mute'}>{muted ? '🔇' : '🔊'}</button>
      <button onClick={onExit} style={{ ...btn, fontSize: 12, padding: '6px 14px' }}>✕ Exit</button>
    </div>
  )
}
