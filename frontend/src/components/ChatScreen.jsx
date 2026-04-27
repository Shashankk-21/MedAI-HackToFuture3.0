import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { ArrowLeft, Loader2, SendHorizonal } from 'lucide-react'

function ChatScreen({ explanation, onBack }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content:
        "Hi! I've reviewed your chest X-ray results. Ask me anything about them.",
    },
  ])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    const trimmed = inputValue.trim()
    if (!trimmed || isLoading) return

    const userMessage = { role: 'user', content: trimmed }
    const updatedMessages = [...messages, userMessage]

    setMessages(updatedMessages)
    setInputValue('')
    setIsLoading(true)

    try {
      // Build history array — everything except the first assistant greeting
      // so the model knows what's already been said
      const history = updatedMessages.slice(1).map((m) => ({
        role: m.role,
        content: m.content,
      }))

      const payload = {
        message: trimmed,
        context: explanation ?? '',
        history,
      }

      const response = await axios.post('http://localhost:8000/chat', payload, {
        headers: { 'Content-Type': 'application/json' },
      })

      const assistantReply =
        response?.data?.response ??
        response?.data?.reply ??
        response?.data?.message ??
        'I received your message but no response was returned.'

      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: assistantReply },
      ])
    } catch (requestError) {
      const backendDetail = requestError?.response?.data?.detail
      const statusCode = requestError?.response?.status
      const debugSuffix = backendDetail
        ? ` (API ${statusCode}: ${backendDetail})`
        : ''

      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `I couldn't reach the assistant right now. Please try again.${debugSuffix}`,
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleInputKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      handleSend()
    }
  }

  return (
    <main className="flex min-h-screen flex-col bg-slate-900 text-slate-300">
      <header className="flex items-center gap-4 border-b border-slate-700 bg-slate-800 p-4">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-900/50 px-3 py-2 text-sm font-medium text-slate-200 transition hover:border-cyan-500 hover:text-cyan-300"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Results
        </button>
        <h1 className="text-lg font-semibold text-slate-100 sm:text-xl">
          Medical Assistant
        </h1>
      </header>

      <section className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}`}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] px-4 py-3 text-sm leading-relaxed sm:max-w-[70%] ${
                message.role === 'user'
                  ? 'rounded-l-xl rounded-tr-xl bg-cyan-600 text-white'
                  : 'rounded-r-xl rounded-tl-xl bg-slate-800 text-slate-200'
              }`}
            >
              {message.content}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="inline-flex items-center gap-2 rounded-r-xl rounded-tl-xl bg-slate-800 px-4 py-3 text-sm text-slate-200">
              <Loader2 className="h-4 w-4 animate-spin" />
              Thinking...
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </section>

      <footer className="border-t border-slate-700 bg-slate-800 p-4">
        <div className="mx-auto flex w-full max-w-5xl items-center gap-3">
          <input
            type="text"
            value={inputValue}
            onChange={(event) => setInputValue(event.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder="Ask about your scan results..."
            className="h-11 flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-cyan-500 focus:ring-2 focus:ring-cyan-500/30"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={isLoading || !inputValue.trim()}
            className="inline-flex h-11 items-center gap-2 rounded-lg bg-cyan-500 px-5 font-semibold text-slate-900 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-70"
          >
            <SendHorizonal className="h-4 w-4" />
            Send
          </button>
        </div>
      </footer>
    </main>
  )
}

export default ChatScreen