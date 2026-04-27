# Guide to Hooking Up the Backend

In the previous versions of the frontend to allow you to visualize the beautiful new interface without needing the backend running, we temporarily "mocked" (simulated) the `axios` API calls using `setTimeout()`. This is why the chatbot responded instantly with a pre-written text, and why the analysis results returned mock predictions.

Now that we want to connect this to your real FastAPI backend, you just need to revert those mocks to the actual `axios.post` calls.

## Step 1: Update `UploadScreen.jsx`

In `src/components/UploadScreen.jsx`, locate the `handleAnalyze` function.

**Replace the "Mock" block with the real API call:**

```javascript
  const handleAnalyze = async () => {
    setIsLoading(true)
    setError('')

    // Spin the loader
    gsap.to(iconRef.current, { rotation: "+=360", repeat: -1, duration: 1, ease: "linear" })

    // Provide a fallback mock URL if no file was selected (optional, for safety)
    const imagePreviewUrl = selectedFile ? URL.createObjectURL(selectedFile) : 'https://images.unsplash.com/photo-1579684385127-1ef15d508118?q=80&w=800&auto=format&fit=crop'

    // --- REAL BACKEND CONNECTION ---
    if (!selectedFile) {
        setError('Please select a file first.');
        setIsLoading(false);
        gsap.killTweensOf(iconRef.current);
        return;
    }

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      // Point this to your FastAPI server URL
      const response = await axios.post('http://localhost:8000/analyze', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      })

      const predictions = response?.data?.predictions ?? {}
      const explanation = response?.data?.explanation ?? ''

      // Animate out before calling completion
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
        requestError?.response?.data?.detail ||
          'Could not analyze the scan. Please check your connection to the server.'
      )
    } finally {
      setIsLoading(false)
    }
    // --------------------------------
  }
```

## Step 2: Update `ChatScreen.jsx`

In `src/components/ChatScreen.jsx`, locate the `handleSend` function.

**Replace the "Mock" block with the real API call:**

```javascript
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

    // --- REAL BACKEND CONNECTION ---
    try {
      const payload = {
        message: trimmed,
        context: explanation, // Make sure your FastAPI backend accepts this!
        explanation,
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
          content: `I am currently unable to reach the server to analyze that question. Please try again later.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
        },
      ])
    } finally {
      setIsLoading(false)
    }
    // --------------------------------
  }
```

## How to test:
Make sure your FastAPI server is running in another terminal. Make sure you have configured CORS securely in FastAPI to accept connections from your frontend (usually `http://localhost:3000` or `http://localhost:5173` depending on Vite configuration). The frontend will now successfully hit your actual live FastAPI backend.
