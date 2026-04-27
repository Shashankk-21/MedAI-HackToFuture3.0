import { useEffect, useRef, useState } from 'react'
import axios from 'axios'
import { ArrowLeft, Send, Sparkles, Bot, Clock } from 'lucide-react'
import { gsap } from 'gsap'

const BotAvatar = ({ isThinking }) => (
  <div className="relative inline-flex items-center justify-center w-12 h-12 rounded-full bg-gradient-to-br from-indigo-500 via-cyan-500 to-emerald-400 p-[2px] shadow-lg">
    <div className="w-full h-full rounded-full bg-white dark:bg-slate-900 flex items-center justify-center overflow-hidden">
      <Bot className={`w-6 h-6 text-cyan-600 dark:text-cyan-400 ${isThinking ? 'animate-pulse' : ''}`} />
    </div>
    {isThinking && (
      <span className="absolute -top-1 -right-1 flex h-4 w-4">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75"></span>
        <span className="relative inline-flex rounded-full h-4 w-4 bg-cyan-500"></span>
      </span>
    )}
  </div>
)

const TypingIndicator = () => (
  <div className="flex items-center gap-1.5 px-2 py-1">
    <div className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '0ms' }} />
    <div className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '150ms' }} />
    <div className="w-2 h-2 rounded-full bg-slate-400 animate-bounce" style={{ animationDelay: '300ms' }} />
  </div>
)

function ChatScreen({ explanation, onBack }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! I am Zenith, your medical AI assistant. I have reviewed your scan results. How can I help you understand them better?',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    },
  ])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const bottomRef = useRef(null)
  const [showSuggestions, setShowSuggestions] = useState(true)
  const messagesEndRef = useRef(null)
  
  const MAX_CHARS = 500
  
  const suggestions = [
    "What is the main finding in simple terms?",
    "Should I be worried about these results?",
    "What should be my next medical step?"
  ]

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    
    // Animate newest messages
    const bubbles = document.querySelectorAll('.message-bubble:not(.animated)')
    if (bubbles.length > 0) {
      gsap.fromTo(bubbles, { opacity: 0, y: 10, scale: 0.95 }, { opacity: 1, y: 0, scale: 1, duration: 0.3, stagger: 0.1, ease: 'back.out(1.2)' })
      bubbles.forEach(b => b.classList.add('animated'))
    }
  }, [messages, isLoading])

  const handleSend = async (overrideText = null) => {
    const textToSend = overrideText || inputValue
    const trimmed = textToSend.trim()
    if (!trimmed || isLoading) return

    setShowSuggestions(false)
    const userMsg = { 
      role: 'user', 
      content: trimmed,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    setMessages((prev) => [...prev, userMsg])
    if (!overrideText) setInputValue('')
    setIsLoading(true)

    try {
      const payload = {
        message: trimmed,
        context: explanation, 
      }

      const response = await axios.post('http://localhost:8000/chat', payload, {
        headers: { 'Content-Type': 'application/json' },
      })

      let assistantReply = response?.data?.response ?? response?.data?.reply ?? response?.data?.message 
      if (!assistantReply) assistantReply = "I received your message, but no response text was returned."
      
      setMessages((prev) => [
        ...prev,
        { 
          role: 'assistant', 
          content: assistantReply,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        },
      ])
    } catch (requestError) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `I am currently unable to reach the server. Please try again later.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleInputKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSend()
    }
  }

  return (
    <main className="flex h-screen flex-col dark:bg-slate-900 bg-slate-50 font-sans">
      {/* Header */}
      <header className="flex-shrink-0 border-b dark:border-slate-800 border-slate-200 dark:bg-slate-900/80 bg-white/80 backdrop-blur-md px-4 py-3 sm:px-6 z-10 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="p-2 rounded-full dark:hover:bg-slate-800 hover:bg-slate-200 transition-colors text-slate-500"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div className="flex items-center gap-3">
            <BotAvatar isThinking={isLoading} />
            <div>
              <h1 className="font-bold font-serif text-lg dark:text-slate-100 text-slate-800 leading-tight">Zenith Bot</h1>
              <span className="text-xs font-semibold text-emerald-500 flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Online
              </span>
            </div>
          </div>
        </div>
        <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-full dark:bg-slate-800 bg-slate-100 border dark:border-slate-700 border-slate-200">
          <Sparkles className="w-3.5 h-3.5 text-cyan-500" />
          <span className="text-xs font-medium text-slate-500">Powered by Gemini AI</span>
        </div>
      </header>

      {/* Chat Area */}
      <section className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
        <div className="max-w-4xl mx-auto space-y-6">
          {messages.map((message, index) => {
            const isUser = message.role === 'user'
            return (
              <div key={index} className={`message-bubble flex flex-col ${isUser ? 'items-end' : 'items-start'} ${index === 0 ? 'animated' : ''}`}>
                <div className={`flex items-end gap-2 max-w-[85%] sm:max-w-[75%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
                  {!isUser && (
                    <div className="w-8 h-8 rounded-full bg-cyan-100 dark:bg-cyan-900/40 flex items-center justify-center flex-shrink-0 shadow-sm border border-cyan-200 dark:border-cyan-800">
                      <Bot className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
                    </div>
                  )}
                  
                  <div className={`px-5 py-3.5 rounded-2xl shadow-sm text-[15px] leading-relaxed ${
                    isUser 
                      ? 'bg-gradient-to-br from-cyan-600 to-blue-600 text-white rounded-br-sm' 
                      : 'bg-white dark:bg-slate-800 border dark:border-slate-700 border-slate-200 dark:text-slate-200 text-slate-700 rounded-bl-sm'
                  }`}>
                    {message.content}
                  </div>
                </div>
                
                <div className={`flex items-center gap-1 mt-1.5 px-10 ${isUser ? 'justify-end' : 'justify-start'} text-[11px] text-slate-400 font-medium`}>
                  <Clock className="w-3 h-3" />
                  {message.timestamp}
                </div>
                
                {/* Suggestions specifically after the very first bot msg */}
                {!isUser && index === 0 && showSuggestions && (
                  <div className="mt-4 ml-10 flex flex-wrap gap-2">
                    {suggestions.map((suggestion, i) => (
                      <button
                        key={i}
                        onClick={() => handleSend(suggestion)}
                        className="text-left px-4 py-2 rounded-full text-sm font-medium border border-cyan-200 dark:border-cyan-800/50 dark:bg-cyan-900/20 bg-cyan-50 dark:text-cyan-300 text-cyan-700 hover:bg-cyan-100 dark:hover:bg-cyan-800/40 transition-colors shadow-sm"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )
          })}

          {isLoading && (
            <div className="flex flex-col items-start">
              <div className="flex items-end gap-2 max-w-[85%] sm:max-w-[75%]">
                <div className="w-8 h-8 rounded-full bg-cyan-100 dark:bg-cyan-900/40 flex items-center justify-center flex-shrink-0 border border-cyan-200 dark:border-cyan-800">
                  <Bot className="w-4 h-4 text-cyan-600 dark:text-cyan-400" />
                </div>
                <div className="px-4 py-3.5 rounded-2xl rounded-bl-sm bg-white dark:bg-slate-800 border dark:border-slate-700 border-slate-200">
                  <TypingIndicator />
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </section>

      {/* Input Area */}
      <footer className="flex-shrink-0 bg-white dark:bg-slate-800 border-t dark:border-slate-700 border-slate-200 p-4 sm:p-6 z-10 shadow-[0_-10px_40px_rgba(0,0,0,0.05)] dark:shadow-[0_-10px_40px_rgba(0,0,0,0.2)]">
        <div className="max-w-4xl mx-auto relative">
          <textarea
            value={inputValue}
            onChange={(e) => {
              if (e.target.value.length <= MAX_CHARS) {
                setInputValue(e.target.value)
              }
            }}
            onKeyDown={handleInputKeyDown}
            placeholder="Type your question here... (Shift+Enter for new line)"
            className="w-full bg-slate-50 dark:bg-slate-900 border dark:border-slate-700 border-slate-300 rounded-2xl py-4 pl-4 pr-16 text-slate-800 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-cyan-500/50 resize-none font-sans"
            rows="2"
          />
          <div className="absolute right-3 top-3 bottom-0 flex flex-col justify-end pb-3 items-end">
            <button
              onClick={() => handleSend(null)}
              disabled={isLoading || !inputValue.trim()}
              className="p-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-white shadow-md disabled:bg-slate-300 dark:disabled:bg-slate-700 disabled:shadow-none transition-all duration-200 mb-1"
            >
              <Send className="w-5 h-5" />
            </button>
            <span className={`text-[10px] font-medium mr-1 ${inputValue.length >= MAX_CHARS ? 'text-red-500' : 'text-slate-400'}`}>
              {inputValue.length}/{MAX_CHARS}
            </span>
          </div>
        </div>
      </footer>
    </main>
  )
}

export default ChatScreen