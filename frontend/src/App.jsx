import { useEffect, useState, useRef } from 'react'
import { gsap } from 'gsap'
import { Moon, Sun } from 'lucide-react'
import ChatScreen from './components/ChatScreen'
import ResultsScreen from './components/ResultsScreen'
import UploadScreen from './components/UploadScreen'

function App() {
  const [currentScreen, setCurrentScreen] = useState('upload')
  const [predictions, setPredictions] = useState(null)
  const [explanation, setExplanation] = useState('')
  const [imagePreviewUrl, setImagePreviewUrl] = useState('')
  const [isDarkMode, setIsDarkMode] = useState(true)
  const screenRef = useRef(null)

  useEffect(() => {
    return () => {
      if (imagePreviewUrl) {
        URL.revokeObjectURL(imagePreviewUrl)
      }
    }
  }, [imagePreviewUrl])

  // GSAP Transition on screen change
  useEffect(() => {
    if (screenRef.current) {
      gsap.fromTo(
        screenRef.current,
        { opacity: 0, y: 20 },
        { opacity: 1, y: 0, duration: 0.5, ease: "power3.out" }
      )
    }
  }, [currentScreen])

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
    <div className={`min-h-screen transition-colors duration-300 font-sans flex flex-col ${isDarkMode ? 'dark bg-[#0B1120] text-slate-100' : 'bg-slate-50 text-slate-900'}`}>
      <div className="dark:bg-[#0B1120] bg-slate-50 min-h-screen flex flex-col">
        {/* Header Section */}
        <header className="flex justify-between items-end border-b dark:border-slate-800 border-slate-200 pb-4 px-8 pt-8 mb-8 sticky top-0 z-50 dark:bg-[#0B1120]/80 bg-slate-50/80 backdrop-blur-md">
          <div className="flex flex-col cursor-pointer" onClick={handleReset}>
            <h1 className="text-4xl sm:text-5xl font-serif font-black tracking-tighter dark:text-white text-slate-900">ZENITH</h1>
            <p className="text-[10px] uppercase tracking-[0.3em] dark:text-cyan-400 text-cyan-600 font-bold opacity-80">Multimodal Diagnostic AI</p>
          </div>
          <div className="flex gap-4 sm:gap-6 items-center">
            <div className="hidden sm:flex flex-col items-end">
              <span className="text-[10px] uppercase tracking-widest text-slate-400">Patient ID</span>
              <span className="font-mono text-sm font-bold dark:text-cyan-200 text-cyan-700">#PX-9928-ALPHA</span>
            </div>
            <div className="h-10 w-auto sm:w-24 dark:bg-slate-900 bg-slate-200 border dark:border-slate-700 border-slate-300 rounded-full flex items-center p-1 justify-center px-1 sm:justify-start">
              <button
                onClick={toggleTheme}
                className="h-8 w-8 dark:bg-cyan-500 bg-cyan-600 rounded-full dark:shadow-[0_0_15px_rgba(34,211,238,0.5)] shadow-md flex items-center justify-center transition-transform hover:scale-105"
                aria-label="Toggle theme"
              >
                {isDarkMode ? <Sun className="w-4 h-4 text-[#0B1120] fill-current" /> : <Moon className="w-4 h-4 text-white fill-current" />}
              </button>
            </div>
          </div>
        </header>

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
