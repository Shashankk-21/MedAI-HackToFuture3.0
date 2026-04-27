import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { Activity, Loader2, UploadCloud, X, FileImage, AlertTriangle } from 'lucide-react'
import { gsap } from 'gsap'

function UploadScreen({ onAnalysisComplete }) {
  const fileInputRef = useRef(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')
  const [scanType, setScanType] = useState('xray')
  const containerRef = useRef(null)
  const iconRef = useRef(null)

  useEffect(() => {
    // Initial load animation
    gsap.fromTo(
      containerRef.current,
      { opacity: 0, scale: 0.95 },
      { opacity: 1, scale: 1, duration: 0.6, ease: "power3.out" }
    )
  }, [])

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
    if (!file) return

    setError('')
    setSelectedFile(file)
    
    // Quick scale bounce when file added
    gsap.fromTo(
      containerRef.current,
      { scale: 0.98 },
      { scale: 1, duration: 0.3, ease: "back.out(1.5)" }
    )
  }

  const handleDrop = (event) => {
    event.preventDefault()
    if (isLoading) return

    const droppedFile = event.dataTransfer.files?.[0]
    handleFileSelected(droppedFile)
  }

  const openFilePicker = () => {
    if (isLoading) return
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
  setIsLoading(true)
  setError('')

  gsap.to(iconRef.current, { rotation: "+=360", repeat: -1, duration: 1, ease: "linear" })

  if (!selectedFile) {
    setError('Please select a file first.')
    setIsLoading(false)
    gsap.killTweensOf(iconRef.current)
    return
  }

  const imagePreviewUrl = URL.createObjectURL(selectedFile)
  const formData = new FormData()
  formData.append('file', selectedFile)

  try {
    const response = await axios.post('http://localhost:8000/analyze', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })

    const predictions = response?.data?.predictions ?? {}
    const explanation = response?.data?.explanation ?? ''

    gsap.to(containerRef.current, {
      opacity: 0,
      y: -20,
      duration: 0.4,
      ease: "power2.in",
      onComplete: () => {
        onAnalysisComplete(predictions, explanation, imagePreviewUrl)
      }
    })
  } catch (requestError) {
    gsap.killTweensOf(iconRef.current)
    setError(
      requestError?.response?.data?.detail || 'Could not analyze the scan. Check server connection.'
    )
  } finally {
    setIsLoading(false)
  }
}
  // Hover animations for the dropzone
  const onDragEnter = () => {
    gsap.to(iconRef.current, { scale: 1.1, y: -5, duration: 0.2 })
  }
  const onDragLeave = () => {
    gsap.to(iconRef.current, { scale: 1, y: 0, duration: 0.2 })
  }

  return (
    <main className="flex flex-1 items-center justify-center py-4">
      <section 
        ref={containerRef}
        className="w-full max-w-3xl rounded-2xl border dark:border-slate-800 border-slate-300 dark:bg-slate-900/40 bg-white p-8 sm:p-10 shadow-lg dark:shadow-cyan-900/5 backdrop-blur-md"
      >
        <header className="mb-10 text-center">
          <div className="inline-flex items-center justify-center p-3 rounded-full dark:bg-cyan-950 bg-cyan-100 mb-4 border dark:border-cyan-500/20">
            <Activity className="h-8 w-8 text-cyan-500" />
          </div>
          <h2 className="text-3xl font-serif font-black tracking-tighter dark:text-slate-100 text-slate-800 sm:text-4xl mb-3">
            SECURE SCAN ANALYSIS
          </h2>
          <p className="text-[11px] uppercase tracking-widest text-slate-500 dark:text-slate-400 font-bold mb-6">
            Upload a chest X-Ray or CT scan for AI-assisted diagnostic insights.
          </p>
          <div className="flex justify-center">
            <div className="bg-slate-200 dark:bg-slate-900/50 p-1 border dark:border-slate-700 border-slate-300 rounded-lg inline-flex">
              <button 
                className={`px-4 py-2 rounded-md text-xs font-bold uppercase tracking-wider transition-colors ${scanType === 'xray' ? 'bg-cyan-600 text-white shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'}`}
                onClick={() => setScanType('xray')}
              >
                Chest X-Ray
              </button>
              <button 
                className={`px-4 py-2 rounded-md text-xs font-bold uppercase tracking-wider transition-colors ${scanType === 'ct' ? 'bg-cyan-600 text-white shadow-sm' : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200'}`}
                onClick={() => setScanType('ct')}
              >
                CT Scan
              </button>
            </div>
          </div>
        </header>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(event) => handleFileSelected(event.target.files?.[0])}
        />

        {scanType === 'ct' ? (
          <div className="flex h-80 w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed dark:border-slate-700 border-slate-300 dark:bg-slate-900/30 bg-slate-50/50 px-6 text-center">
            <AlertTriangle className="h-16 w-16 text-yellow-500 drop-shadow-[0_0_15px_rgba(234,179,8,0.3)] mb-4" />
            <h3 className="text-xl font-bold dark:text-slate-200 text-slate-800 font-serif mb-2">CT Scan Mode Coming Soon</h3>
            <p className="max-w-md text-sm leading-relaxed text-slate-500 dark:text-slate-400 font-sans">
              The current model is optimized exclusively for chest X-rays. CT support is in development and is not enabled in this version.
            </p>
          </div>
        ) : !selectedFile ? (
          <button
            type="button"
            onClick={openFilePicker}
            onDrop={handleDrop}
            onDragOver={(event) => event.preventDefault()}
            onDragEnter={onDragEnter}
            onDragLeave={onDragLeave}
            className="group relative flex h-80 w-full flex-col items-center justify-center rounded-2xl border-2 border-dashed dark:border-slate-700 border-slate-300 dark:bg-slate-900/30 bg-slate-50/50 px-6 text-center transition-all duration-300 hover:border-cyan-500/50 dark:hover:bg-slate-800/40 hover:bg-cyan-50 focus:outline-none"
          >
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.05),transparent_70%)] opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none rounded-2xl" />
            <div ref={iconRef}>
              <UploadCloud className="h-16 w-16 text-cyan-500 drop-shadow-[0_0_15px_rgba(34,211,238,0.3)]" />
            </div>
            <p className="mt-6 text-lg font-bold text-slate-700 dark:text-slate-300 font-serif">
              Drag & drop your medical image
            </p>
            <p className="mt-2 max-w-md text-sm leading-relaxed text-slate-500 dark:text-slate-400 font-sans">
              Supports JPG, PNG formats up to 20MB. Clear, well-lit scans yield the highest confidence scores.
            </p>
            <div className="mt-6 inline-flex border border-slate-700 rounded-full dark:bg-slate-800 bg-slate-200 px-5 py-2 text-[11px] uppercase tracking-widest font-bold text-slate-700 dark:text-slate-300 transition group-hover:bg-cyan-500 group-hover:border-cyan-400 group-hover:text-white shadow-sm">
              BROWSE FILES
            </div>
          </button>
        ) : (
          <div className="relative overflow-hidden rounded-2xl border dark:border-slate-700 border-slate-300 bg-slate-50 dark:bg-black shadow-inner shadow-cyan-900/10 min-h-[320px]">
             <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.1),transparent_70%)] pointer-events-none"></div>
            <img
              src={previewUrl || undefined}
              alt="Scan preview"
              className="absolute inset-0 w-full h-full object-contain p-4 mix-blend-screen"
            />

            <div className="absolute top-0 left-0 w-full p-4 flex justify-between items-start bg-gradient-to-b from-black/80 to-transparent">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-slate-900/60 backdrop-blur-md border border-cyan-500/20 text-white font-mono text-xs">
                <FileImage className="w-4 h-4 text-cyan-400" />
                {selectedFile.name}
              </div>
              <button
                type="button"
                onClick={clearSelection}
                className="h-10 w-10 bg-black/60 backdrop-blur-md rounded-full border border-white/10 flex items-center justify-center text-white hover:bg-red-500/80 transition-colors z-10"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}

        <button
          type="button"
          disabled={isLoading || scanType === 'ct'}
          onClick={handleAnalyze}
          className="mt-8 flex w-full items-center justify-center rounded-xl bg-cyan-600 hover:bg-cyan-500 px-5 py-4 text-sm font-bold tracking-widest uppercase text-white shadow-[0_4px_20px_rgba(8,145,178,0.3)] transition-all duration-300 disabled:bg-slate-700 disabled:shadow-none disabled:text-slate-500 disabled:cursor-not-allowed"
        >
          {isLoading ? (
            <span className="inline-flex items-center gap-3">
              <Loader2 className="h-5 w-5 animate-spin text-white" />
              ANALYZING MATRIX...
            </span>
          ) : (
            'START ANALYSIS'
          )}
        </button>

        {error && (
          <div className="mt-5 rounded-xl border border-red-200 dark:border-red-500/30 bg-red-50 dark:bg-red-950/40 px-5 py-4 text-sm text-red-600 dark:text-red-300 flex items-start gap-3">
            <X className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <p leading-relaxed>{error}</p>
          </div>
        )}
      </section>
    </main>
  )
}

export default UploadScreen
