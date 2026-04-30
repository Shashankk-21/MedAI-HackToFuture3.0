import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { Activity, Loader2, UploadCloud, X, FileImage, AlertTriangle, Heart } from 'lucide-react'
import { gsap } from 'gsap'

const API_URL = import.meta.env.VITE_API_URL


function UploadScreen({ onAnalysisComplete }) {
  const fileInputRef = useRef(null)
  const [selectedFile, setSelectedFile] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [previewUrl, setPreviewUrl] = useState('')
  const [scanType, setScanType] = useState('xray')
  const containerRef = useRef(null)
  const iconRef = useRef(null)

  // --- ANIMATION ENGINE ---
  useEffect(() => {
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

  // Load a sample image from the public /samples/ folder and inject it
  // into the upload flow as if the user selected it.
  const loadSample = async (url, filename) => {
    try {
      setIsLoading(true)
      setError('')
      const res = await fetch(url)
      if (!res.ok) throw new Error('Failed to fetch sample')
      const blob = await res.blob()
      const file = new File([blob], filename, { type: blob.type || 'image/jpeg' })
      handleFileSelected(file)
    } catch (err) {
      setError('Could not load sample image.')
    } finally {
      setIsLoading(false)
    }
  }

  // --- BACKEND LOGIC: FASTAPI CONNECTION ---
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

    console.log('DEBUG: Vite Env Variables', {
      'import.meta.env.VITE_API_URL': import.meta.env.VITE_API_URL,
      'API_URL': API_URL
    })

    try {
      const response = await axios.post(`${API_URL}/analyze`, formData, {
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

  const onDragEnter = () => {
    gsap.to(iconRef.current, { scale: 1.1, y: -5, duration: 0.2 })
  }
  const onDragLeave = () => {
    gsap.to(iconRef.current, { scale: 1, y: 0, duration: 0.2 })
  }

  return (
    <div className="min-h-screen flex flex-col font-sans dark:bg-[#05070a] bg-slate-50 transition-colors duration-500">
      <main className="flex flex-1 items-center justify-center py-12 relative z-10 px-4">
        
        {/* Glow Effects */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-indigo-500/10 rounded-full blur-[120px] pointer-events-none opacity-50" />
        <div className="absolute top-1/2 left-1/2 -translate-x-1/4 -translate-y-3/4 w-[400px] h-[400px] bg-purple-500/10 rounded-full blur-[100px] pointer-events-none opacity-40" />

        <div className="w-full max-w-7xl flex gap-6 lg:gap-12 items-center justify-center">
          {/* LEFT SIDE: CLINICAL SCOPE - 7 DISEASES */}
          <div className="hidden lg:flex flex-col justify-center flex-1">
            <div className="group">
              <h3 className="text-lg font-serif font-black uppercase tracking-[0.2em] text-slate-600 dark:text-zinc-600 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 mb-6 transition-colors duration-300 opacity-40 group-hover:opacity-100">Clinical Scope</h3>
              <ul className="space-y-3.5">
                {['Pneumonia', 'Lung Opacity', 'Effusion', 'Consolidation', 'Atelectasis', 'Cardiomegaly', 'Edema'].map((disease, idx) => (
                  <li key={idx} className="text-xl font-serif font-semibold text-slate-700 dark:text-zinc-500 group-hover:text-slate-900 dark:group-hover:text-zinc-200 flex items-center gap-3 transition-all duration-300 opacity-40 group-hover:opacity-100">
                    <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 group-hover:bg-indigo-400 flex-shrink-0 shadow-[0_0_12px_rgba(99,102,241,0.5)] group-hover:shadow-[0_0_16px_rgba(99,102,241,0.8)] transition-all duration-300"></span>
                    <span>{disease}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* CENTER: UPLOAD BOX - ORIGINAL SIZE AND FUNCTIONALITY */}
          <section 
            ref={containerRef}
            className="w-full max-w-2xl flex-shrink-0 relative rounded-[2.5rem] border dark:border-white/10 border-slate-200/60 dark:bg-white/[0.03] bg-white/90 p-8 sm:p-12 shadow-2xl backdrop-blur-3xl"
          >
          <header className="mb-10 text-center">
            <div className="inline-flex items-center justify-center p-4 rounded-3xl dark:bg-indigo-950/50 bg-indigo-100 mb-6 border dark:border-indigo-500/30 border-indigo-200">
              <Activity className="h-8 w-8 text-indigo-500" />
            </div>
            <h2 className="text-4xl font-serif font-black tracking-tighter dark:text-white text-slate-900 sm:text-5xl mb-4">
              SECURE <span className="text-indigo-500">SCAN</span> ANALYSIS
            </h2>
            <p className="text-[12px] uppercase tracking-[0.3em] text-slate-500 dark:text-zinc-400 font-bold mb-8">
              AI-ASSISTED RADIOLOGY INSIGHTS
            </p>
            
            <div className="flex justify-center relative z-10">
              <div className="dark:bg-black/40 bg-slate-200/50 backdrop-blur-md p-1.5 border dark:border-white/10 border-slate-300/50 rounded-2xl inline-flex shadow-inner">
                <button 
                  className={`px-6 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all duration-300 ${scanType === 'xray' ? 'bg-indigo-600 text-white shadow-[0_0_20px_rgba(79,70,229,0.4)]' : 'text-slate-500 dark:text-zinc-400 hover:text-slate-800 dark:hover:text-zinc-200'}`}
                  onClick={() => setScanType('xray')}
                >
                  Chest X-Ray
                </button>
                <button 
                  className={`px-6 py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider transition-all duration-300 ${scanType === 'ct' ? 'bg-indigo-600 text-white shadow-[0_0_20px_rgba(79,70,229,0.4)]' : 'text-slate-500 dark:text-zinc-400 hover:text-slate-800 dark:hover:text-zinc-200'}`}
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
            <div className="group flex h-80 w-full flex-col items-center justify-center rounded-[2rem] border border-dashed dark:border-white/20 border-slate-300 dark:bg-black/20 bg-slate-50 px-6 text-center transition-all duration-500">
              <AlertTriangle className="h-16 w-16 text-rose-500 drop-shadow-[0_0_20px_rgba(244,63,94,0.4)] mb-5" />
              <h3 className="text-xl font-bold dark:text-zinc-100 text-slate-800 font-serif mb-3">CT Scan Mode Coming Soon</h3>
              <p className="max-w-md text-sm leading-relaxed text-slate-500 dark:text-zinc-400 font-sans">
                Support for CT scans is currently in development.
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
              className="group relative flex h-80 w-full flex-col items-center justify-center rounded-[2rem] border-2 border-dashed dark:border-white/10 border-slate-300 dark:bg-black/20 bg-slate-50 px-6 text-center transition-all duration-500 hover:border-indigo-500/50 dark:hover:bg-white/5 hover:bg-indigo-50/50 focus:outline-none overflow-hidden"
            >
              <div ref={iconRef}>
                <UploadCloud className="h-20 w-20 text-indigo-500 drop-shadow-[0_10px_20px_rgba(99,102,241,0.3)]" />
              </div>
              <p className="mt-8 text-xl font-bold text-slate-700 dark:text-zinc-200 font-serif">
                Drag & drop medical image
              </p>
              <div className="mt-8 inline-flex items-center border border-zinc-700 dark:bg-zinc-900 bg-white px-8 py-3 rounded-2xl text-[12px] uppercase tracking-widest font-black text-slate-700 dark:text-zinc-200 transition-all group-hover:bg-indigo-600 group-hover:border-indigo-500 group-hover:text-white group-hover:scale-105 shadow-xl">
                BROWSE FILES
              </div>
            </button>
          ) : (
            <div className="relative overflow-hidden rounded-[2rem] border dark:border-zinc-800 border-slate-300 bg-black min-h-[350px] flex items-center justify-center">
              <img
                src={previewUrl || undefined}
                alt="Scan preview"
                className="w-full h-full object-contain p-6 mix-blend-screen"
              />

              <div className="absolute top-0 left-0 w-full p-6 flex justify-between items-start bg-gradient-to-b from-black/90 to-transparent">
                <div className="flex items-center gap-3 px-4 py-2 rounded-xl bg-zinc-900/80 backdrop-blur-xl border border-white/10 text-white font-mono text-[10px]">
                  <FileImage className="w-4 h-4 text-indigo-400" />
                  {selectedFile.name.length > 20 ? selectedFile.name.substring(0,20) + '...' : selectedFile.name}
                </div>
                <button
                  type="button"
                  onClick={clearSelection}
                  className="h-12 w-12 bg-black/60 backdrop-blur-md rounded-2xl border border-white/10 flex items-center justify-center text-white hover:bg-rose-500/80 transition-all z-10"
                >
                  <X className="w-6 h-6" />
                </button>
              </div>
            </div>
          )}

          {/* --- SAMPLE DOWNLOADS: Light, subtle pills below the upload zone --- */}
          <div className="mt-6 flex flex-col items-center gap-3">
            <p className="text-sm text-slate-500 dark:text-zinc-400 mb-2 font-medium">Don't have an X-ray? Try our samples.</p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => loadSample('/samples/Pneumonia_positive.jpeg', 'Pneumonia_positive.jpeg')}
                className="px-3 py-1.5 rounded-full border border-slate-300 dark:border-white/10 text-xs font-semibold text-slate-700 dark:text-zinc-300 bg-transparent hover:bg-indigo-50/30 transition"
              >
                Pneumonia Sample
              </button>
              <button
                type="button"
                onClick={() => loadSample('/samples/Normal.jpeg', 'Normal.jpeg')}
                className="px-3 py-1.5 rounded-full border border-slate-300 dark:border-white/10 text-xs font-semibold text-slate-700 dark:text-zinc-300 bg-transparent hover:bg-indigo-50/30 transition"
              >
                Normal Sample
              </button>
              <button
                type="button"
                onClick={() => loadSample('/samples/Covid_Positive.jpeg', 'Covid_Positive.jpeg')}
                className="px-3 py-1.5 rounded-full border border-slate-300 dark:border-white/10 text-xs font-semibold text-slate-700 dark:text-zinc-300 bg-transparent hover:bg-indigo-50/30 transition"
              >
                COVID Sample
              </button>
            </div>
          </div>

          <button
            type="button"
            disabled={isLoading || scanType === 'ct'}
            onClick={handleAnalyze}
            className="mt-10 flex w-full items-center justify-center rounded-2xl bg-indigo-600 hover:bg-indigo-500 px-8 py-5 text-sm font-black tracking-[0.2em] uppercase text-white shadow-[0_10px_30px_rgba(79,70,229,0.3)] transition-all duration-500 hover:-translate-y-1 disabled:bg-zinc-800 disabled:shadow-none disabled:text-zinc-600 disabled:cursor-not-allowed"
          >
            {isLoading ? (
              <span className="inline-flex items-center gap-4">
                <Loader2 className="h-6 w-6 animate-spin text-white" />
                PROCESSING RADIOGRAPH...
              </span>
            ) : (
              'INITIALIZE AI ANALYSIS'
            )}
          </button>

          {error && (
            <div className="mt-6 rounded-2xl border border-rose-500/20 bg-rose-500/5 px-6 py-4 text-sm text-rose-500 flex items-start gap-4">
              <AlertTriangle className="w-5 h-5 flex-shrink-0 mt-0.5" />
              <p className="font-medium">{error}</p>
            </div>
          )}
        </section>

          {/* RIGHT SIDE: SYSTEM ARCHITECTURE */}
          <div className="hidden lg:flex flex-col justify-center flex-1">
            <div className="group text-right">
              <h3 className="text-lg font-serif font-black uppercase tracking-[0.2em] text-slate-600 dark:text-zinc-600 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 mb-6 transition-colors duration-300 opacity-40 group-hover:opacity-100">System Architecture</h3>
              <ul className="space-y-3.5">
                {[
                  { label: 'Dataset', value: 'NIH + CheXpert' },
                  { label: 'Architecture', value: 'DenseNet121' },
                  { label: 'Preprocessing', value: 'CLAHE' }
                ].map((item, idx) => (
                  <li key={idx} className="transition-all duration-300 opacity-40 group-hover:opacity-100">
                    <p className="text-sm font-serif font-medium text-slate-500 dark:text-zinc-600 group-hover:text-indigo-600 dark:group-hover:text-indigo-400 mb-1 transition-colors duration-300">{item.label}</p>
                    <p className="text-xl font-serif font-semibold text-slate-700 dark:text-zinc-500 group-hover:text-slate-900 dark:group-hover:text-zinc-200 flex items-center justify-end gap-3 transition-colors duration-300">
                      <span>{item.value}</span>
                      <span className="w-2.5 h-2.5 rounded-full bg-indigo-500 group-hover:bg-indigo-400 flex-shrink-0 shadow-[0_0_12px_rgba(99,102,241,0.5)] group-hover:shadow-[0_0_16px_rgba(99,102,241,0.8)] transition-all duration-300"></span>
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </main>

      {/* --- CLEAN ZENITH FOOTER --- */}
      <footer className="w-full py-12 px-6 border-t dark:border-white/5 border-slate-200 relative overflow-hidden">
        <div className="max-w-7xl mx-auto flex flex-col items-center gap-6 relative z-10">
          <div className="text-center">
            <h3 className="text-2xl font-serif font-black tracking-tighter dark:text-white text-slate-900">
              ZENITH<span className="text-indigo-500">.</span>
            </h3>
            <p className="text-xs text-slate-500 dark:text-zinc-500 mt-2 font-medium tracking-wide">
              Advanced Multimodal Medical Diagnostic Tool
            </p>
          </div>

          <div className="text-center">
            <p className="text-xs font-bold text-slate-800 dark:text-zinc-300 tracking-[0.2em] uppercase mb-2">
              © 2026 ZENITH <span className="mx-2 text-zinc-600">|</span> Made by Team <span className="text-indigo-500 italic">Astralis</span>
            </p>
            <p className="text-[10px] text-slate-500 dark:text-zinc-600 uppercase tracking-widest flex items-center justify-center gap-1.5">
              All rights reserved <span className="mx-1">•</span> Handcrafted with Precision
            </p>
          </div>
        </div>
        <div className="absolute bottom-0 left-1/2 -translate-x-1/2 w-[500px] h-[100px] bg-indigo-500/5 rounded-full blur-[80px] pointer-events-none" />
      </footer>
    </div>
  )
}

export default UploadScreen