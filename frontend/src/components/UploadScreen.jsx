import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { Activity, Loader2, UploadCloud, X } from 'lucide-react'

function UploadScreen({ onAnalysisComplete }) {
  const fileInputRef = useRef(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')

  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl('')
      return
    }

    const url = URL.createObjectURL(selectedFile)
    setPreviewUrl(url)

    return () => {
      URL.revokeObjectURL(url)
    }
  }, [selectedFile])

  const handleFileSelected = (file) => {
    if (!file) {
      return
    }

    setError('')
    setSelectedFile(file)
  }

  const handleDrop = (event) => {
    event.preventDefault()
    if (isLoading) {
      return
    }

    const droppedFile = event.dataTransfer.files?.[0]
    handleFileSelected(droppedFile)
  }

  const openFilePicker = () => {
    if (isLoading) {
      return
    }

    fileInputRef.current?.click()
  }

  const clearSelection = () => {
    setSelectedFile(null)
    setError('')
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const handleAnalyze = async () => {
    if (!selectedFile) {
      setError('Please choose a chest X-ray image before running analysis.')
      return
    }

    setIsLoading(true)
    setError('')

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      const response = await axios.post('http://localhost:8000/analyze', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      const predictions = response?.data?.predictions ?? {}
      const explanation = response?.data?.explanation ?? ''
      const imagePreviewUrl = URL.createObjectURL(selectedFile)

      onAnalysisComplete(predictions, explanation, imagePreviewUrl)
    } catch (requestError) {
      setError(
        requestError?.response?.data?.detail ||
          'Could not analyze the scan. Check that the API server is running at localhost:8000.'
      )
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-900 px-4 py-8 text-slate-300 sm:px-6">
      <section className="w-full max-w-3xl rounded-3xl border border-slate-700 bg-slate-800 p-6 shadow-2xl shadow-cyan-900/30 sm:p-8">
        <header className="mb-8 flex items-center justify-center gap-3 text-center">
          <Activity className="h-8 w-8 text-cyan-500" />
          <h1 className="text-3xl font-bold tracking-tight text-slate-100 sm:text-4xl">
            MedAI Chest Scan Analyzer
          </h1>
        </header>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(event) => handleFileSelected(event.target.files?.[0])}
        />

        {!selectedFile ? (
          <button
            type="button"
            onClick={openFilePicker}
            onDrop={handleDrop}
            onDragOver={(event) => event.preventDefault()}
            className="group flex h-72 w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-600 bg-slate-900/40 px-6 text-center transition hover:border-cyan-500 hover:bg-slate-900 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-slate-800"
          >
            <UploadCloud className="h-14 w-14 text-cyan-500 transition group-hover:scale-105" />
            <p className="mt-4 max-w-md text-base leading-relaxed text-slate-300">
              Drop your chest X-ray here or click to browse
            </p>
          </button>
        ) : (
          <div className="relative overflow-hidden rounded-2xl border border-slate-600 bg-slate-900/40">
            <img
              src={previewUrl}
              alt="Selected chest X-ray preview"
              className="h-72 w-full object-contain"
            />

            <button
              type="button"
              onClick={clearSelection}
              className="absolute right-3 top-3 inline-flex items-center gap-1 rounded-md bg-slate-800/90 px-3 py-1.5 text-xs font-semibold text-slate-100 transition hover:bg-red-600"
            >
              <X className="h-3.5 w-3.5" />
              Remove
            </button>
          </div>
        )}

        <button
          type="button"
          disabled={isLoading || !selectedFile}
          onClick={handleAnalyze}
          className="mt-6 flex w-full items-center justify-center rounded-xl bg-cyan-500 px-5 py-4 text-lg font-semibold text-slate-900 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-70"
        >
          {isLoading ? (
            <span className="inline-flex items-center gap-2">
              <Loader2 className="h-5 w-5 animate-spin" />
              Analyzing your scan...
            </span>
          ) : (
            'Analyze Scan'
          )}
        </button>

        {error && (
          <p className="mt-4 rounded-lg border border-red-500/30 bg-red-950/40 px-4 py-3 text-sm text-red-300">
            {error}
          </p>
        )}
      </section>
    </main>
  )
}

export default UploadScreen
