import { useState, useEffect, useRef } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

// Speech Recognition hook
function useSpeechRecognition() {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [isSupported, setIsSupported] = useState(false)
  const recognitionRef = useRef(null)

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (SpeechRecognition) {
      setIsSupported(true)
      recognitionRef.current = new SpeechRecognition()
      recognitionRef.current.continuous = true
      recognitionRef.current.interimResults = true
      recognitionRef.current.lang = 'en-US'

      recognitionRef.current.onresult = (event) => {
        const current = event.resultIndex
        const result = event.results[current]
        setTranscript(result[0].transcript)
      }

      recognitionRef.current.onend = () => {
        setIsListening(false)
      }

      recognitionRef.current.onerror = (event) => {
        console.error('Speech recognition error:', event.error)
        setIsListening(false)
      }
    }
  }, [])

  const startListening = () => {
    if (recognitionRef.current && !isListening) {
      setTranscript('')
      recognitionRef.current.start()
      setIsListening(true)
    }
  }

  const stopListening = () => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop()
      setIsListening(false)
    }
  }

  return { isListening, transcript, isSupported, startListening, stopListening, setTranscript }
}

// Main App Component
export default function App() {
  const [view, setView] = useState('home') // home, auth, contacts, settings
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [user, setUser] = useState(null)
  const [contacts, setContacts] = useState([])
  const [selectedContact, setSelectedContact] = useState(null)
  const [correctedMessage, setCorrectedMessage] = useState('')
  const [isProcessing, setIsProcessing] = useState(false)
  const [lastResult, setLastResult] = useState(null)
  const [error, setError] = useState(null)

  const speech = useSpeechRecognition()

  // Check auth status on load
  useEffect(() => {
    checkAuth()
    loadContacts()
  }, [])

  const checkAuth = async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/status`)
      const data = await res.json()
      setIsAuthenticated(data.authenticated)
      setUser(data.user)
    } catch (e) {
      console.error('Auth check failed:', e)
    }
  }

  const loadContacts = async () => {
    try {
      const res = await fetch(`${API_BASE}/contacts`)
      const data = await res.json()
      setContacts(data)
    } catch (e) {
      console.error('Failed to load contacts:', e)
    }
  }

  const previewMessage = async (text) => {
    if (!text.trim()) return
    setIsProcessing(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/message/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          raw_text: text,
          recipient: selectedContact?.telegram,
          fix_grammar: true
        })
      })
      const data = await res.json()
      setCorrectedMessage(data.corrected)
      if (data.recipient && !selectedContact) {
        setSelectedContact(data.recipient)
      }
    } catch (e) {
      setError('Failed to process message')
    } finally {
      setIsProcessing(false)
    }
  }

  const sendMessage = async () => {
    if (!correctedMessage.trim()) return
    setIsProcessing(true)
    setError(null)

    try {
      const res = await fetch(`${API_BASE}/message/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          raw_text: speech.transcript || correctedMessage,
          recipient: selectedContact?.telegram || selectedContact,
          fix_grammar: true
        })
      })
      const data = await res.json()
      setLastResult(data)
      
      if (data.success) {
        // Reset for next message
        speech.setTranscript('')
        setCorrectedMessage('')
        setSelectedContact(null)
      } else {
        setError(data.error || 'Failed to send message')
      }
    } catch (e) {
      setError('Failed to send message')
    } finally {
      setIsProcessing(false)
    }
  }

  // Handle speech stop - auto preview
  useEffect(() => {
    if (!speech.isListening && speech.transcript) {
      previewMessage(speech.transcript)
    }
  }, [speech.isListening])

  if (!isAuthenticated && view !== 'auth') {
    return <AuthView onSuccess={() => { checkAuth(); setView('home') }} apiBase={API_BASE} />
  }

  return (
    <div className="app">
      <Header user={user} onNavigate={setView} currentView={view} />
      
      {view === 'home' && (
        <main className="main-content">
          {/* Contact Selection */}
          <div className="contact-select">
            <label>Send to:</label>
            <select 
              value={selectedContact?.id || ''} 
              onChange={(e) => {
                const contact = contacts.find(c => c.id === e.target.value)
                setSelectedContact(contact)
              }}
            >
              <option value="">Auto-detect from message</option>
              {contacts.map(c => (
                <option key={c.id} value={c.id}>{c.name} ({c.telegram})</option>
              ))}
            </select>
          </div>

          {/* Voice Input */}
          <div className="voice-section">
            <button 
              className={`mic-button ${speech.isListening ? 'listening' : ''}`}
              onClick={speech.isListening ? speech.stopListening : speech.startListening}
              disabled={!speech.isSupported}
            >
              <MicIcon />
              {speech.isListening ? 'Listening...' : 'Tap to Speak'}
            </button>
            {!speech.isSupported && (
              <p className="warning">Speech recognition not supported in this browser</p>
            )}
          </div>

          {/* Transcript */}
          {speech.transcript && (
            <div className="transcript-box">
              <label>You said:</label>
              <p className="transcript">{speech.transcript}</p>
            </div>
          )}

          {/* Corrected Message */}
          {correctedMessage && (
            <div className="corrected-box">
              <label>Corrected message:</label>
              <textarea 
                value={correctedMessage}
                onChange={(e) => setCorrectedMessage(e.target.value)}
                rows={3}
              />
              {selectedContact && (
                <p className="recipient-info">
                  → To: {selectedContact.name || selectedContact}
                </p>
              )}
            </div>
          )}

          {/* Send Button */}
          {correctedMessage && (
            <button 
              className="send-button"
              onClick={sendMessage}
              disabled={isProcessing}
            >
              {isProcessing ? 'Sending...' : '✈️ Send Message'}
            </button>
          )}

          {/* Error */}
          {error && <div className="error-box">{error}</div>}

          {/* Success */}
          {lastResult?.success && (
            <div className="success-box">
              ✅ Message sent to {lastResult.recipient_name}!
            </div>
          )}

          {/* Manual Text Input */}
          <div className="manual-input">
            <label>Or type your message:</label>
            <textarea
              placeholder="Send to Imran saying the project is ready for review..."
              value={speech.transcript}
              onChange={(e) => speech.setTranscript(e.target.value)}
              rows={2}
            />
            <button onClick={() => previewMessage(speech.transcript)} disabled={isProcessing}>
              Preview
            </button>
          </div>
        </main>
      )}

      {view === 'contacts' && (
        <ContactsView 
          contacts={contacts} 
          onUpdate={loadContacts}
          apiBase={API_BASE}
        />
      )}

      {view === 'settings' && (
        <SettingsView user={user} />
      )}
    </div>
  )
}

// Header Component
function Header({ user, onNavigate, currentView }) {
  return (
    <header className="header">
      <h1>💬 ChatEasezy</h1>
      <nav>
        <button 
          className={currentView === 'home' ? 'active' : ''} 
          onClick={() => onNavigate('home')}
        >
          Home
        </button>
        <button 
          className={currentView === 'contacts' ? 'active' : ''} 
          onClick={() => onNavigate('contacts')}
        >
          Contacts
        </button>
        <button 
          className={currentView === 'settings' ? 'active' : ''} 
          onClick={() => onNavigate('settings')}
        >
          Settings
        </button>
      </nav>
      {user && <span className="user-badge">@{user.username}</span>}
    </header>
  )
}

// Auth View Component
function AuthView({ onSuccess, apiBase }) {
  const [step, setStep] = useState('credentials') // credentials, code, 2fa
  const [apiId, setApiId] = useState('')
  const [apiHash, setApiHash] = useState('')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState(null)

  const startAuth = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const res = await fetch(`${apiBase}/auth/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_id: parseInt(apiId),
          api_hash: apiHash,
          phone: phone
        })
      })
      const data = await res.json()

      if (data.success) {
        if (data.already_authorized) {
          onSuccess()
        } else {
          setStep('code')
        }
      } else {
        setError(data.error || 'Failed to start authentication')
      }
    } catch (e) {
      setError('Connection failed. Is the backend running?')
    } finally {
      setIsLoading(false)
    }
  }

  const completeAuth = async () => {
    setIsLoading(true)
    setError(null)

    try {
      const res = await fetch(`${apiBase}/auth/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, password: password || undefined })
      })
      const data = await res.json()

      if (data.success) {
        onSuccess()
      } else if (data.needs_2fa) {
        setStep('2fa')
      } else {
        setError(data.error || 'Authentication failed')
      }
    } catch (e) {
      setError('Connection failed')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="auth-view">
      <div className="auth-card">
        <h2>🔐 Connect to Telegram</h2>
        
        {step === 'credentials' && (
          <>
            <p>Enter your Telegram API credentials from <a href="https://my.telegram.org" target="_blank">my.telegram.org</a></p>
            <input
              type="number"
              placeholder="API ID"
              value={apiId}
              onChange={(e) => setApiId(e.target.value)}
            />
            <input
              type="text"
              placeholder="API Hash"
              value={apiHash}
              onChange={(e) => setApiHash(e.target.value)}
            />
            <input
              type="tel"
              placeholder="Phone (+919561616168)"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
            />
            <button onClick={startAuth} disabled={isLoading || !apiId || !apiHash || !phone}>
              {isLoading ? 'Connecting...' : 'Connect'}
            </button>
          </>
        )}

        {step === 'code' && (
          <>
            <p>Enter the verification code sent to your Telegram app</p>
            <input
              type="text"
              placeholder="Verification Code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              autoFocus
            />
            <button onClick={completeAuth} disabled={isLoading || !code}>
              {isLoading ? 'Verifying...' : 'Verify'}
            </button>
          </>
        )}

        {step === '2fa' && (
          <>
            <p>Two-factor authentication is enabled. Enter your password.</p>
            <input
              type="password"
              placeholder="2FA Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoFocus
            />
            <button onClick={completeAuth} disabled={isLoading || !password}>
              {isLoading ? 'Verifying...' : 'Complete Login'}
            </button>
          </>
        )}

        {error && <div className="error-box">{error}</div>}
      </div>
    </div>
  )
}

// Contacts View Component
function ContactsView({ contacts, onUpdate, apiBase }) {
  const [name, setName] = useState('')
  const [telegram, setTelegram] = useState('')
  const [role, setRole] = useState('colleague')
  const [isAdding, setIsAdding] = useState(false)

  const addContact = async () => {
    if (!name || !telegram) return
    setIsAdding(true)

    try {
      await fetch(`${apiBase}/contacts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, telegram, role })
      })
      setName('')
      setTelegram('')
      onUpdate()
    } catch (e) {
      console.error('Failed to add contact:', e)
    } finally {
      setIsAdding(false)
    }
  }

  const deleteContact = async (id) => {
    if (!confirm('Delete this contact?')) return

    try {
      await fetch(`${apiBase}/contacts/${id}`, { method: 'DELETE' })
      onUpdate()
    } catch (e) {
      console.error('Failed to delete contact:', e)
    }
  }

  return (
    <div className="contacts-view">
      <h2>👥 Contacts</h2>
      
      <div className="add-contact-form">
        <input
          type="text"
          placeholder="Name (e.g., Imran Shaikh)"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          type="text"
          placeholder="Telegram (@username)"
          value={telegram}
          onChange={(e) => setTelegram(e.target.value)}
        />
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="colleague">Colleague</option>
          <option value="boss">Boss</option>
          <option value="friend">Friend</option>
          <option value="other">Other</option>
        </select>
        <button onClick={addContact} disabled={isAdding || !name || !telegram}>
          {isAdding ? 'Adding...' : '+ Add Contact'}
        </button>
      </div>

      <div className="contacts-list">
        {contacts.length === 0 ? (
          <p className="empty">No contacts yet. Add your first contact above!</p>
        ) : (
          contacts.map(contact => (
            <div key={contact.id} className="contact-card">
              <div className="contact-info">
                <strong>{contact.name}</strong>
                <span className="telegram">{contact.telegram}</span>
                <span className={`role ${contact.role}`}>{contact.role}</span>
              </div>
              <button className="delete-btn" onClick={() => deleteContact(contact.id)}>
                🗑️
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// Settings View Component
function SettingsView({ user }) {
  return (
    <div className="settings-view">
      <h2>⚙️ Settings</h2>
      
      <div className="settings-section">
        <h3>Telegram Account</h3>
        {user ? (
          <div className="user-info">
            <p><strong>Name:</strong> {user.first_name} {user.last_name}</p>
            <p><strong>Username:</strong> @{user.username}</p>
            <p><strong>ID:</strong> {user.id}</p>
          </div>
        ) : (
          <p>Not connected</p>
        )}
      </div>

      <div className="settings-section">
        <h3>About</h3>
        <p>ChatEasezy v1.0.0</p>
        <p>Personal Telegram assistant with AI grammar correction</p>
      </div>
    </div>
  )
}

// Microphone Icon Component
function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor">
      <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5zm6 6c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
    </svg>
  )
}
