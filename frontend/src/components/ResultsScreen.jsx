import { useEffect, useRef } from 'react'
import { gsap } from 'gsap'
import { 
  ArrowRight, 
  Printer, 
  X, 
  CheckCircle2,
  Stethoscope,
  HeartPulse,
  Thermometer,
  AlertTriangle,
  Info 
} from 'lucide-react'

// Severity Donut Component
const SeverityDonut = ({ score }) => {
  const radius = 40
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - score * circumference
  
  let color = "text-emerald-500"
  let bg = "text-emerald-500/20"
  let label = "Low Risk"
  if (score > 0.3) {
    color = "text-yellow-500"
    bg = "text-yellow-500/20"
    label = "Moderate"
  }
  if (score > 0.7) {
    color = "text-red-500"
    bg = "text-red-500/20"
    label = "High Risk"
  }

  const circleRef = useRef(null)

  useEffect(() => {
    gsap.fromTo(
      circleRef.current,
      { strokeDashoffset: circumference },
      { strokeDashoffset, duration: 1.5, ease: "power3.out" }
    )
  }, [score, strokeDashoffset, circumference])

  return (
    <div className="flex flex-col items-center justify-center p-4">
      <div className="relative w-32 h-32 flex items-center justify-center">
        <svg className="transform -rotate-90 w-full h-full">
          <circle cx="64" cy="64" r={radius} stroke="currentColor" strokeWidth="12" fill="transparent" className={bg} />
          <circle 
            ref={circleRef}
            cx="64" 
            cy="64" 
            r={radius} 
            stroke="currentColor" 
            strokeWidth="12" 
            fill="transparent" 
            strokeDasharray={circumference}
            strokeLinecap="round"
            className={`${color} transition-colors duration-300`} 
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold dark:text-slate-100 text-slate-800 font-sans">{Math.round(score * 100)}%</span>
        </div>
      </div>
      <span className={`mt-2 font-semibold ${color}`}>{label}</span>
    </div>
  )
}

function getIconForDisease(diseaseName) {
  const name = diseaseName.toLowerCase()
  if (name.includes('cardiomegaly') || name.includes('heart')) return HeartPulse
  if (name.includes('pneumonia') || name.includes('opacity') || name.includes('lung')) return Stethoscope
  if (name.includes('fever')) return Thermometer
  return AlertTriangle
}

function getGradientBarColor(score) {
  if (score < 0.3) return 'from-green-500 to-green-400'
  if (score <= 0.6) return 'from-green-500 to-yellow-500'
  return 'from-orange-500 to-red-500 shadow-[0_0_10px_rgba(239,68,68,0.5)]'
}

function getScoreColors(score) {
  if (score < 0.3) return { bg: 'dark:bg-green-500/10 bg-green-100', text: 'text-green-500', valText: 'dark:text-green-400 text-green-600' }
  if (score <= 0.6) return { bg: 'dark:bg-yellow-500/10 bg-yellow-100', text: 'text-yellow-500', valText: 'dark:text-yellow-400 text-yellow-600' }
  return { bg: 'dark:bg-red-500/10 bg-red-100', text: 'text-red-500', valText: 'dark:text-red-400 text-red-600' }
}

function ResultsScreen({ predictions, explanation, imagePreviewUrl, onStartChat, onReset }) {
  const containerRef = useRef(null)
  const resultsRef = useRef(null)

  // Normalize data
  const scoreEntries = Object.entries(predictions?.scores ?? {})
    .map(([disease, score]) => [disease, Number(score)])
    .filter(([, score]) => Number.isFinite(score))
    .sort((a, b) => b[1] - a[1])

  const maxSeverity = scoreEntries.length > 0 ? scoreEntries[0][1] : 0
  const topFinding = scoreEntries.length > 0 ? scoreEntries[0] : null

  useEffect(() => {
    // Stagger animation for result cards
    if (resultsRef.current) {
      const cards = resultsRef.current.querySelectorAll('.result-card')
      const bars = resultsRef.current.querySelectorAll('.confidence-fill')
      
      gsap.fromTo(
        cards,
        { opacity: 0, x: 20 },
        { opacity: 1, x: 0, duration: 0.5, stagger: 0.1, ease: "power2.out", delay: 0.2 }
      )

      gsap.fromTo(
        bars,
        { width: "0%" },
        { 
          width: (i, el) => el.dataset.width, 
          duration: 1.2, 
          ease: "power3.out", 
          delay: 0.5 
        }
      )
    }
  }, [scoreEntries])

  const handlePrint = () => {
    window.print()
  }

  return (
    <main ref={containerRef} className="w-full flex-1 flex flex-col font-sans mb-4">
      <div className="flex-1 grid grid-cols-1 md:grid-cols-12 gap-8 min-h-0">
        
        {/* Left Pane: Image */}
        <div className="md:col-span-5 flex flex-col gap-4 min-h-0">
          <div className="relative flex-1 bg-black rounded-2xl border border-slate-700 overflow-hidden shadow-2xl group min-h-[300px] sm:min-h-[400px]">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(34,211,238,0.1),transparent_70%)] pointer-events-none"></div>
            
            {imagePreviewUrl ? (
              <img
                src={imagePreviewUrl}
                alt="Analyzed chest X-ray"
                className="absolute inset-0 w-full h-full object-contain p-4 mix-blend-screen"
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center p-8">
                <div className="w-full h-full border border-slate-800/50 rounded-lg flex flex-col items-center justify-center opacity-40">
                  <span className="font-mono text-xs uppercase tracking-tighter text-slate-500">No Image Data</span>
                </div>
              </div>
            )}
            
            <button
              onClick={onReset}
              className="absolute top-4 right-4 h-10 w-10 bg-black/60 backdrop-blur-md rounded-full border border-white/10 flex items-center justify-center text-white hover:bg-red-500/80 transition-colors z-10"
              title="Close and upload new image"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="absolute bottom-4 left-4 flex items-center gap-2 px-3 py-1.5 bg-cyan-900/50 backdrop-blur-md border border-cyan-400/30 rounded-full z-10">
              <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></div>
              <span className="text-[11px] font-bold text-cyan-50 tracking-wide uppercase">Chest X-Ray Detected ✓</span>
            </div>
          </div>
          
          <div className="p-4 dark:bg-slate-900/50 bg-slate-100 border dark:border-slate-800 border-slate-200 rounded-xl">
            <h4 className="text-[10px] uppercase font-bold text-slate-500 dark:text-slate-500 mb-2">Scan Metadata</h4>
            <div className="grid grid-cols-2 gap-4 text-xs font-mono">
              <div className="flex justify-between font-bold dark:text-slate-400 text-slate-600"><span className="uppercase text-slate-500">Exposure</span><span>88.4 kVp</span></div>
              <div className="flex justify-between font-bold dark:text-slate-400 text-slate-600"><span className="uppercase text-slate-500">Orientation</span><span>PA VIEW</span></div>
            </div>
          </div>
        </div>

        {/* Right Pane: Results */}
        <div className="md:col-span-7 flex flex-col gap-6 min-h-0" ref={resultsRef}>
          {/* Findings Summary */}
          <div className="bg-gradient-to-r dark:from-cyan-950/40 from-cyan-50 dark:to-slate-900 to-white p-5 rounded-2xl border dark:border-cyan-500/20 border-cyan-500/30 shadow-lg">
            <div className="flex items-center gap-3 mb-2">
              <Stethoscope className="w-5 h-5 text-cyan-500 dark:text-cyan-400" />
              <h3 className="font-bold text-slate-800 dark:text-cyan-50">Primary Diagnostic Summary</h3>
            </div>
            <p className="dark:text-slate-300 text-slate-700 text-sm leading-relaxed whitespace-pre-wrap">
              {explanation || "Awaiting AI interpretation..."}
            </p>
          </div>

          {/* Detailed Confidence Scores */}
          <div className="flex-1 dark:bg-slate-900/30 bg-white border dark:border-slate-800 border-slate-200 rounded-2xl p-6 flex flex-col min-h-0 shadow-sm">
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-[11px] uppercase tracking-[0.2em] font-bold text-slate-500 shadow-none">Disease Probability Matrix</h3>
              <button onClick={handlePrint} className="text-[10px] dark:bg-slate-800 bg-slate-100 px-3 py-1 rounded border dark:border-slate-700 border-slate-300 dark:hover:bg-slate-700 hover:bg-slate-200 dark:text-slate-200 text-slate-700 font-bold transition-colors">
                PRINT REPORT
              </button>
            </div>
            
            <div className="space-y-5 overflow-y-auto pr-2 mb-6">
              {scoreEntries.length === 0 ? (
                <p className="text-sm text-slate-500">No predictions found.</p>
              ) : (
                scoreEntries.map(([disease, score]) => {
                  const percentage = Math.round(score * 100)
                  const Icon = getIconForDisease(disease)
                  const colors = getScoreColors(score)
                  
                  return (
                    <div key={disease} className="result-card space-y-2 opacity-0">
                      <div className="flex justify-between items-center">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded ${colors.bg} flex items-center justify-center ${colors.text}`}>
                            <Icon className="w-5 h-5" />
                          </div>
                          <span className="text-sm font-semibold dark:text-slate-200 text-slate-800">{disease}</span>
                        </div>
                        <span className={`font-mono text-sm font-bold ${colors.valText}`}>{percentage}%</span>
                      </div>
                      <div className="h-2 w-full dark:bg-slate-800 bg-slate-200 rounded-full overflow-hidden">
                        <div
                          data-width={`${percentage}%`}
                          className={`confidence-fill h-full rounded-full bg-gradient-to-r ${getGradientBarColor(score)}`}
                          style={{ width: "0%" }}
                        />
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            {/* Assistant CTA Area */}
            <div className="mt-auto pt-6 border-t dark:border-slate-800 border-slate-200">
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-4 gap-4">
                 <div className="flex items-center gap-3">
                    <div className="h-10 w-10 bg-cyan-500 rounded-full flex items-center justify-center ring-4 dark:ring-cyan-500/20 ring-cyan-500/10">
                      <span className="text-white font-serif font-black">Z</span>
                    </div>
                    <div>
                      <p className="text-[10px] text-cyan-600 dark:text-cyan-400 font-bold uppercase tracking-widest">Zenith AI Assistant</p>
                      <p className="text-sm dark:text-white text-slate-800 font-semibold">Do you have questions about these results?</p>
                    </div>
                 </div>
                 <button 
                  onClick={onStartChat}
                  className="w-full sm:w-auto px-6 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white font-bold rounded-xl shadow-[0_4px_20px_rgba(8,145,178,0.3)] transition-all flex items-center justify-center gap-2 uppercase tracking-wide text-[11px]"
                 >
                   Consult Assistant
                   <ArrowRight className="w-4 h-4" />
                 </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Footer Warning */}
      <footer className="mt-4 text-[10px] text-slate-500 text-center uppercase tracking-widest font-bold">
        Disclaimer: High-confidence model prediction. Not a definitive medical diagnosis. Please consult a qualified physician.
      </footer>
    </main>
  )
}

export default ResultsScreen