import { useEffect, useState, useRef } from 'react'
import { gsap } from 'gsap'
import { Moon, Sun } from 'lucide-react'
import ChatScreen from './components/ChatScreen'
import ResultsScreen from './components/ResultsScreen'
import UploadScreen from './components/UploadScreen'

function App() {
  // --- ORIGINAL LOGIC: STATE ---
  const [currentScreen, setCurrentScreen] = useState('upload')
  const [predictions, setPredictions] = useState(null)
  const [explanation, setExplanation] = useState('')
  const [imagePreviewUrl, setImagePreviewUrl] = useState('')
  const [isDarkMode, setIsDarkMode] = useState(true)
  
  // --- ORIGINAL LOGIC: REFS ---
  const screenRef = useRef(null)
  const appContainerRef = useRef(null) // From design for spotlight

  // --- ORIGINAL LOGIC: IMAGE CLEANUP ---
  useEffect(() => {
    return () => {
      if (imagePreviewUrl) {
        URL.revokeObjectURL(imagePreviewUrl)
      }
    }
  }, [imagePreviewUrl])

  // --- DESIGN LOGIC: MOUSE TRACKING SPOTLIGHT ---
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (appContainerRef.current) {
        appContainerRef.current.style.setProperty('--mouse-x', `${e.clientX}px`)
        appContainerRef.current.style.setProperty('--mouse-y', `${e.clientY}px`)
      }
    }
    window.addEventListener('mousemove', handleMouseMove)
    return () => window.removeEventListener('mousemove', handleMouseMove)
  }, [])

  // --- ORIGINAL LOGIC: GSAP TRANSITIONS ---
  useEffect(() => {
    if (screenRef.current) {
      gsap.fromTo(
        screenRef.current,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }
      )
    }
  }, [currentScreen])

  // --- ORIGINAL LOGIC: HANDLERS ---
  const handleAnalysisComplete = (
    nextPredictions,
    nextExplanation,
    nextImagePreviewUrl
  ) => {
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl)
    }
    setPredictions(nextPredictions)
    setExplanation(nextExplanation)
    setImagePreviewUrl(nextImagePreviewUrl)
    setCurrentScreen('results')
  }

  const handleStartChat = () => {
    setCurrentScreen('chat')
  }

  const handleBackToResults = () => {
    setCurrentScreen('results')
  }

  const handleReset = () => {
    if (imagePreviewUrl) {
      URL.revokeObjectURL(imagePreviewUrl)
      setImagePreviewUrl('')
    }
    setPredictions(null)
    setExplanation('')
    setCurrentScreen('upload')
  }

  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode)
  }

  return (
    <div 
      ref={appContainerRef} 
      className={`relative min-h-screen transition-colors duration-500 font-sans flex flex-col ${isDarkMode ? 'dark bg-[#030712] text-zinc-100' : 'bg-[#F4F6F8] text-slate-900'} overflow-hidden`}
    >
      {/* DESIGN VISUALS: Spotlight & Scanline Backgrounds */}
      <div 
        className="pointer-events-none fixed inset-0 z-0 transition-opacity duration-500" 
        style={{
          background: `radial-gradient(800px circle at var(--mouse-x, 50%) var(--mouse-y, 50%), ${isDarkMode ? 'rgba(79, 70, 229, 0.08)' : 'rgba(186, 230, 253, 0.4)'}, transparent 40%)`
        }} 
      />
      <div className={`pointer-events-none fixed inset-0 z-[60] opacity-[0.02] ${isDarkMode ? 'opacity-[0.03]' : 'opacity-[0.02]'}`} style={{ backgroundImage: 'repeating-linear-gradient(0deg, transparent, transparent 2px, #000 2px, #000 4px)' }} />

      <div className="relative z-10 min-h-screen flex flex-col">
        
        {/* DESIGN VISUALS: Header Section */}
        <header className="flex justify-between items-end border-b dark:border-zinc-800/60 border-slate-200/60 pb-4 px-8 pt-8 mb-8 sticky top-0 z-50 dark:bg-[#030712]/80 bg-[#F4F6F8]/80 backdrop-blur-md">
          <div className="flex flex-col cursor-pointer group" onClick={handleReset}>
            <h1 className="text-4xl sm:text-5xl font-serif font-black tracking-tighter dark:text-white text-slate-900 group-hover:text-indigo-500 transition-colors">
              ZENITH
            </h1>
            <p className="text-[10px] uppercase tracking-[0.3em] dark:text-indigo-400 text-indigo-600 font-bold opacity-80">
              Multimodal Diagnostic AI
            </p>
          </div>

          <div className="flex gap-4 sm:gap-6 items-center">
            <div className="hidden sm:flex flex-col items-end">
              <span className="text-[10px] uppercase tracking-widest text-slate-400">Patient ID</span>
              <span className="font-mono text-sm font-bold dark:text-rose-300 text-rose-600">#PX-9928-ALPHA</span>
            </div>

            {/* DESIGN VISUALS: Modern Sliding Toggle */}
            <button
              onClick={toggleTheme}
              className="relative inline-flex h-8 w-14 items-center rounded-full transition-colors duration-300 focus:outline-none dark:bg-zinc-800 bg-slate-300 dark:border-zinc-700 border-slate-200 border shadow-inner"
              aria-label="Toggle theme"
            >
              <span
                className={`inline-flex h-6 w-6 transform items-center justify-center rounded-full dark:bg-zinc-900 bg-white transition-transform duration-500 shadow-xl ${
                  isDarkMode ? 'translate-x-7' : 'translate-x-1'
                }`}
              >
                {isDarkMode ? (
                  <Moon className="h-3.5 w-3.5 text-indigo-400 fill-current" />
                ) : (
                  <Sun className="h-4 w-4 text-amber-500 fill-current" />
                )}
              </span>
            </button>
          </div>
        </header>

        {/* ORIGINAL LOGIC: Screen Rendering with screenRef for GSAP */}
        <div ref={screenRef} className="pb-10 flex-1 flex flex-col px-4 sm:px-8">
          {currentScreen === 'upload' && (
            <UploadScreen onAnalysisComplete={handleAnalysisComplete} />
          )}

          {currentScreen === 'results' && (
            <ResultsScreen
              predictions={predictions}
              explanation={explanation}
              imagePreviewUrl={imagePreviewUrl}
              onStartChat={handleStartChat}
              onReset={handleReset}
            />
          )}

          {currentScreen === 'chat' && (
            <ChatScreen explanation={explanation} onBack={handleBackToResults} />
          )}
        </div>
      </div>
    </div>
  )
}

export default App