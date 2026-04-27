function getBarColor(score) {
  if (score < 0.3) {
    return 'bg-emerald-500'
  }

  if (score <= 0.6) {
    return 'bg-yellow-500'
  }

  return 'bg-red-500'
}

function ResultsScreen({ predictions, explanation, imagePreviewUrl, onStartChat }) {
  const scoreEntries = Object.entries(predictions?.scores ?? {})
    .map(([disease, score]) => [disease, Number(score)])
    .filter(([, score]) => Number.isFinite(score))
    .sort((a, b) => b[1] - a[1])

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-900 px-4 py-8 text-slate-300 sm:px-6">
      <section className="w-full max-w-6xl rounded-3xl border border-slate-700 bg-slate-800 p-5 shadow-2xl shadow-cyan-900/30 sm:p-8">
        <div className="grid gap-6 md:grid-cols-2 md:gap-8">
          <article className="rounded-2xl border border-slate-700 bg-slate-900/50 p-4">
            {imagePreviewUrl ? (
              <img
                src={imagePreviewUrl}
                alt="Uploaded chest X-ray"
                className="h-full max-h-[520px] w-full rounded-xl object-contain"
              />
            ) : (
              <div className="flex h-72 items-center justify-center rounded-xl border border-slate-700 bg-slate-900/50 text-sm text-slate-400">
                No X-ray preview available.
              </div>
            )}
          </article>

          <article className="rounded-2xl border border-slate-700 bg-slate-900/50 p-5 sm:p-6">
            <h1 className="text-2xl font-semibold text-slate-100">Analysis Results</h1>

            {scoreEntries.length === 0 ? (
              <p className="mt-4 text-sm text-slate-400">No score data found in predictions.scores.</p>
            ) : (
              <div className="mt-5 space-y-4">
                {scoreEntries.map(([disease, score]) => {
                  const percentage = Math.round(score * 100)

                  return (
                    <div key={disease}>
                      <div className="mb-2 flex items-center justify-between text-sm">
                        <span className="font-medium text-slate-200">{disease}</span>
                        <span className="font-semibold text-cyan-300">{percentage}%</span>
                      </div>

                      <div className="h-3 w-full overflow-hidden rounded-full bg-slate-700">
                        <div
                          className={`h-full rounded-full transition-all duration-700 ${getBarColor(
                            score
                          )}`}
                          style={{ width: `${score * 100}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            <div className="mt-6 rounded-lg bg-slate-800 p-4 text-sm leading-relaxed text-slate-300">
              {explanation || 'No explanation returned by the model.'}
            </div>

            <button
              type="button"
              onClick={onStartChat}
              className="mt-6 w-full rounded-xl bg-cyan-500 px-5 py-3 font-semibold text-slate-900 transition hover:bg-cyan-400"
            >
              Ask the Assistant
            </button>
          </article>
        </div>
      </section>
    </main>
  )
}

export default ResultsScreen
