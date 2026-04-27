import { useEffect, useState } from 'react'
import ChatScreen from './components/ChatScreen'
import ResultsScreen from './components/ResultsScreen'
import UploadScreen from './components/UploadScreen'

function App() {
  const [currentScreen, setCurrentScreen] = useState('upload')
  const [predictions, setPredictions] = useState(null)
  const [explanation, setExplanation] = useState('')
  const [imagePreviewUrl, setImagePreviewUrl] = useState('')

  useEffect(() => {
    return () => {
      if (imagePreviewUrl) {
        URL.revokeObjectURL(imagePreviewUrl)
      }
    }
  }, [imagePreviewUrl])

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

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {currentScreen === 'upload' && (
        <UploadScreen onAnalysisComplete={handleAnalysisComplete} />
      )}

      {currentScreen === 'results' && (
        <ResultsScreen
          predictions={predictions}
          explanation={explanation}
          imagePreviewUrl={imagePreviewUrl}
          onStartChat={handleStartChat}
        />
      )}

      {currentScreen === 'chat' && (
        <ChatScreen explanation={explanation} onBack={handleBackToResults} />
      )}
    </div>
  )
}

export default App
