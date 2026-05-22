import { useEffect, useRef, useState } from 'react'
import { DEMO_STEPS, type DemoStep } from './demoScript'
import SpotlightOverlay from './SpotlightOverlay'

type Phase = 'entry' | 'running' | 'finished'

export default function DemoMode() {
  const [phase,   setPhase]   = useState<Phase>('entry')
  const [stepIdx, setStepIdx] = useState(0)
  const [muted,   setMuted]   = useState(false)
  const [paused,  setPaused]  = useState(false)
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null)

  // Force light/dark navy gradient on the demo entry
  useEffect(() => { document.body.style.background = '#07172B' }, [])

  function speak(text: string, onEnd: () => void) {
    if (muted || !('speechSynthesis' in window)) { onEnd(); return }
    window.speechSynthesis.cancel()
    const utt = new SpeechSynthesisUtterance(text)
    const voices = window.speechSynthesis.getVoices()
    const preferred =
      voices.find(v => v.name.includes('Samantha')) ||
      voices.find(v => v.name.includes('Google US English')) ||
      voices.find(v => v.lang === 'en-US')
    if (preferred) utt.voice = preferred
    utt.rate = 0.93
    utt.pitch = 1.0
    utt.volume = 0.9
    utt.onend = onEnd
    utteranceRef.current = utt
    window.speechSynthesis.speak(utt)
  }

  // Navigate + narrate when step changes
  useEffect(() => {
    if (phase !== 'running') return
    const step = DEMO_STEPS[stepIdx]
    if (!step) { setPhase('finished'); return }
    // We're on /demo route — emit a navigate event so the dashboard shows
    // the right screen. The dashboard listens via tgc:navigate.
    window.dispatchEvent(new CustomEvent('tgc:navigate', { detail: step.screen }))
    if (paused) return
    speak(step.narration, () => {
      if (paused) return
      // auto-advance unless it's the last
      if (stepIdx === DEMO_STEPS.length - 1) setPhase('finished')
      else setStepIdx(stepIdx + 1)
    })
    return () => { if (utteranceRef.current) window.speechSynthesis.cancel() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepIdx, phase, paused, muted])

  function start()  { setPhase('running'); setStepIdx(0) }
  function next()   { window.speechSynthesis.cancel(); setStepIdx(Math.min(stepIdx + 1, DEMO_STEPS.length - 1)) }
  function prev()   { window.speechSynthesis.cancel(); setStepIdx(Math.max(stepIdx - 1, 0)) }
  function pause()  { setPaused(p => !p); if (!paused) window.speechSynthesis.cancel() }
  function stop()   { window.speechSynthesis.cancel(); setPhase('entry'); setStepIdx(0) }

  if (phase === 'entry') return <EntryScreen onStart={start} />
  if (phase === 'finished') return <FinishedScreen onRestart={start} />

  const step: DemoStep = DEMO_STEPS[stepIdx]
  return (
    <>
      <SpotlightOverlay selector={step.spotlightSelector} />
      {muted && <Caption text={step.narration} />}
      <DemoControls
        stepIdx={stepIdx} total={DEMO_STEPS.length}
        onPrev={prev} onNext={next} onPause={pause} onStop={stop}
        onToggleMute={() => setMuted(!muted)} muted={muted} paused={paused}
      />
    </>
  )
}

function EntryScreen({ onStart }: { onStart: () => void }) {
  return (
    <div className="min-h-screen flex items-center justify-center p-4"
         style={{ background: 'linear-gradient(135deg, #1A3A5C 0%, #07172B 100%)' }}>
      <div className="text-center max-w-lg">
        <div className="text-gold font-display font-bold text-6xl tracking-wide">INNtelligence</div>
        <div className="text-white/70 text-sm tracking-wide mt-1">by The Gracious Collection</div>
        <div className="text-white text-lg mt-6 font-display">12-Minute Interactive Demo</div>
        <p className="text-white/80 mt-3">
          See INNtelligence managing <strong className="text-gold">Anchorage 1770 Inn</strong>, Beaufort SC.
          12 narrated steps · click through at your own pace.
        </p>
        <div className="mt-8 flex flex-col items-center gap-3">
          <button onClick={onStart}
                  className="bg-gold text-white font-bold px-8 py-3 rounded-lg hover:bg-gold-dark text-lg">
            ▶ Start Demo
          </button>
          <a href="/" className="text-white/50 text-sm hover:text-white">Skip — show me the app</a>
        </div>
      </div>
    </div>
  )
}

function FinishedScreen({ onRestart }: { onRestart: () => void }) {
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-cream">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg p-8 text-center">
        <div className="text-gold font-display text-3xl">Ready to see INNtelligence on your property?</div>
        <p className="text-slate-600 mt-3">14-day free trial. No credit card required. Cancel anytime.</p>
        <div className="mt-6 flex flex-col gap-2">
          <a href="/pricing" className="bg-gold text-white font-bold py-3 rounded-lg hover:bg-gold-dark">Start My Free Trial</a>
          <a href="mailto:jwilliams8559@gmail.com?subject=INNtelligence Demo — I want to learn more"
             className="bg-white border border-navy text-navy font-bold py-3 rounded-lg hover:bg-navy/5">
            Schedule a Call with Jim
          </a>
          <button onClick={onRestart} className="text-xs text-slate-400 mt-3 hover:text-navy">Replay demo</button>
        </div>
      </div>
    </div>
  )
}

function DemoControls({ stepIdx, total, onPrev, onNext, onPause, onStop, onToggleMute, muted, paused }: any) {
  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 bg-navy text-white rounded-xl shadow-2xl px-4 py-2 flex items-center gap-3">
      <button onClick={onPrev} disabled={stepIdx === 0} className="px-2 py-1 hover:text-gold disabled:opacity-30">⏮</button>
      <button onClick={onPause} className="px-2 py-1 hover:text-gold">{paused ? '▶' : '⏸'}</button>
      <button onClick={onNext} disabled={stepIdx === total - 1} className="px-2 py-1 hover:text-gold disabled:opacity-30">⏭</button>
      <div className="text-xs px-3 border-l border-white/20">
        <span className="text-gold font-bold">Step {stepIdx + 1}</span>
        <span className="text-white/60"> of {total}</span>
      </div>
      <div className="flex gap-1">
        {Array.from({ length: total }).map((_, i) => (
          <span key={i} className={`w-1.5 h-1.5 rounded-full ${i === stepIdx ? 'bg-gold' : i < stepIdx ? 'bg-sage' : 'bg-white/30'}`} />
        ))}
      </div>
      <button onClick={onToggleMute} className="px-2 py-1 hover:text-gold border-l border-white/20 pl-3">{muted ? '🔇' : '🔊'}</button>
      <button onClick={onStop} className="px-2 py-1 hover:text-coral">⏹</button>
    </div>
  )
}

function Caption({ text }: { text: string }) {
  return (
    <div className="fixed bottom-20 left-1/2 -translate-x-1/2 z-40 max-w-2xl mx-4 bg-black/70 text-white text-sm px-4 py-2 rounded">
      {text}
    </div>
  )
}
