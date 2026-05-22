/** Wraps the Web Speech API. Picks the best available US English voice
 * (Samantha on macOS, Google US English on Chrome). Survives Chrome's
 * async voice-loading by retrying via the voiceschanged event. */
export class NarrationEngine {
  speak(text: string, onEnd?: () => void): void {
    if (!('speechSynthesis' in window)) {
      onEnd?.()
      return
    }
    window.speechSynthesis.cancel()

    const start = () => {
      const voices = window.speechSynthesis.getVoices()
      const preferred =
           voices.find(v => v.name === 'Samantha')
        || voices.find(v => v.name === 'Google US English')
        || voices.find(v => v.lang === 'en-US' && v.localService)
        || voices.find(v => v.lang.startsWith('en'))
      const utt = new SpeechSynthesisUtterance(text)
      if (preferred) utt.voice = preferred
      utt.rate   = 0.93
      utt.pitch  = 1.0
      utt.volume = 0.9
      utt.onend   = () => onEnd?.()
      utt.onerror = () => onEnd?.()
      window.speechSynthesis.speak(utt)
    }

    if (window.speechSynthesis.getVoices().length === 0) {
      window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.onvoiceschanged = null
        start()
      }
      // Fallback in case voiceschanged never fires
      setTimeout(start, 600)
    } else {
      start()
    }
  }

  cancel(): void {
    if ('speechSynthesis' in window) window.speechSynthesis.cancel()
  }
  pause(): void  { if ('speechSynthesis' in window) window.speechSynthesis.pause() }
  resume(): void { if ('speechSynthesis' in window) window.speechSynthesis.resume() }
}
