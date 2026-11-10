import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, 
  User, 
  Send, 
  RotateCcw, 
  Package, 
  ShoppingBag, 
  Tag, 
  FileText, 
  HelpCircle, 
  Sparkles, 
  LogOut, 
  Plus, 
  Menu, 
  X, 
  Clock, 
  CheckCircle2, 
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  ExternalLink
} from 'lucide-react';
import { marked } from 'marked';

// Configure marked options for clean rendering
marked.setOptions({
  breaks: true,
  gfm: true
});

const API_BASE = import.meta.env.VITE_API_BASE ? import.meta.env.VITE_API_BASE.replace(/\/$/, '') : '';
const DEMO_QUERY_LIMIT = 5;
const DEMO_USER_ID = 200;

// Format active agent name for human display
// Specifically: 'if active agent is return_agent so in the left sidebar for that chat it should look like return'
const formatAgentName = (agentKey) => {
  if (!agentKey) return 'Support';
  const clean = String(agentKey).trim().toLowerCase();
  if (clean === 'return_agent' || clean === 'return') return 'Return';
  if (clean === 'order_agent' || clean === 'order') return 'Order';
  if (clean === 'product_agent' || clean === 'product') return 'Product';
  if (clean === 'coupon_agent' || clean === 'coupon') return 'Coupon';
  if (clean === 'qa_agent' || clean === 'qa' || clean === 'policy_agent') return 'Policy / QA';
  if (clean === 'not_sure' || clean === 'supervisor') return 'Support';
  return clean.replace('_agent', '').replace(/^\w/, (c) => c.toUpperCase());
};

const getAgentBadgeColor = (name) => {
  switch (name) {
    case 'Return':
      return { bg: 'rgba(245, 158, 11, 0.15)', text: '#fbbf24', border: 'rgba(245, 158, 11, 0.3)', icon: RotateCcw };
    case 'Order':
      return { bg: 'rgba(59, 130, 246, 0.15)', text: '#60a5fa', border: 'rgba(59, 130, 246, 0.3)', icon: Package };
    case 'Product':
      return { bg: 'rgba(16, 185, 129, 0.15)', text: '#34d399', border: 'rgba(16, 185, 129, 0.3)', icon: ShoppingBag };
    case 'Coupon':
      return { bg: 'rgba(139, 92, 246, 0.15)', text: '#a78bfa', border: 'rgba(139, 92, 246, 0.3)', icon: Tag };
    case 'Policy / QA':
      return { bg: 'rgba(236, 72, 153, 0.15)', text: '#f472b6', border: 'rgba(236, 72, 153, 0.3)', icon: FileText };
    default:
      return { bg: 'rgba(100, 116, 139, 0.15)', text: '#94a3b8', border: 'rgba(100, 116, 139, 0.3)', icon: Bot };
  }
};

export default function App() {
  // App views: 'landing', 'test_mode', 'chat'
  const [view, setView] = useState('landing');
  const [sessionToken, setSessionToken] = useState(() => localStorage.getItem('session_token') || '');
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('user_profile') || 'null');
    } catch {
      return null;
    }
  });

  // Backend connection status
  const [backendReady, setBackendReady] = useState(false);
  const [checkingBackend, setCheckingBackend] = useState(true);

  // Test mode state
  const [demoSessionId, setDemoSessionId] = useState('');
  const [demoQueryCount, setDemoQueryCount] = useState(0);
  const [demoCustomer, setDemoCustomer] = useState(null);

  // Chat conversation state
  const [threads, setThreads] = useState([]);
  const [currentThreadId, setCurrentThreadId] = useState('');
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  // Processing timer state
  const [timerSeconds, setTimerSeconds] = useState(0);
  const timerRef = useRef(null);

  // Mobile sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Google Login modal / prompt state
  const [showGoogleModal, setShowGoogleModal] = useState(false);
  const [googleEmailInput, setGoogleEmailInput] = useState('');

  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isProcessing, timerSeconds]);

  // Check backend health
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`);
        if (res.ok) {
          setBackendReady(true);
        }
      } catch (err) {
        console.warn('Backend ping error:', err);
      } finally {
        setCheckingBackend(false);
      }
    };
    checkHealth();
  }, []);

  // Timer logic: when processing, track elapsed time; after 5s, start counting 6s, 7s, 8s...
  useEffect(() => {
    if (isProcessing) {
      setTimerSeconds(0);
      const start = Date.now();
      timerRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - start) / 1000);
        setTimerSeconds(elapsed);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setTimerSeconds(0);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isProcessing]);

  // Check existing session token on mount
  useEffect(() => {
    if (sessionToken && !demoSessionId) {
      verifyAndLoadSession();
    }
  }, []);

  const verifyAndLoadSession = async () => {
    try {
      const res = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${sessionToken}` }
      });
      if (res.ok) {
        const userData = await res.json();
        setCurrentUser(userData);
        setView('chat');
        loadThreads(sessionToken);
      } else {
        // Token expired
        logout();
      }
    } catch {
      // Offline / fallback to landing
      setView('landing');
    }
  };

  // Load threads
  const loadThreads = async (token = sessionToken) => {
    try {
      const res = await fetch(`${API_BASE}/chat/threads`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        const threadList = data.threads || [];
        setThreads(threadList);
        if (threadList.length > 0 && !currentThreadId) {
          selectThread(threadList[0].thread_id, token);
        } else if (threadList.length === 0) {
          startNewChat();
        }
      }
    } catch (err) {
      console.error('Failed to load threads:', err);
    }
  };

  // Select a thread and load messages
  const selectThread = async (threadId, token = sessionToken) => {
    setCurrentThreadId(threadId);
    setSidebarOpen(false);
    try {
      const res = await fetch(`${API_BASE}/chat/threads/${threadId}/messages`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      }
    } catch (err) {
      console.error('Failed to load messages for thread:', err);
    }
  };

  // Start a fresh conversation
  const startNewChat = () => {
    const newId = crypto.randomUUID();
    setCurrentThreadId(newId);
    setMessages([]);
    setSidebarOpen(false);
  };

  // Start Test Mode (Recruiter Demo)
  const startTestMode = async () => {
    const newSessionId = crypto.randomUUID();
    setDemoSessionId(newSessionId);
    setDemoQueryCount(0);
    setMessages([
      {
        role: 'assistant',
        content: `👋 **Welcome to BrightCart Support Test Mode!**\n\nYou are acting as **Demo Customer (ID: ${DEMO_USER_ID})**. You can ask up to 5 questions to evaluate our autonomous multi-agent routing.\n\nTry asking:\n- *"Can I return the headphones I ordered?"*\n- *"What items did I order recently?"*\n- *"Do you have any discount coupons available?"*`
      }
    ]);
    setView('test_mode');

    // Fetch demo customer details
    try {
      const res = await fetch(`${API_BASE}/chat/demo-info`);
      if (res.ok) {
        const data = await res.json();
        setDemoCustomer(data);
      }
    } catch (err) {
      console.warn('Could not load demo info:', err);
    }
  };

  // Google Login handling
  const handleGoogleLogin = async (emailToUse) => {
    const email = emailToUse || googleEmailInput.trim() || 'recruiter.demo@brightcart.example';
    try {
      const res = await fetch(`${API_BASE}/auth/google-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: email,
          name: email.split('@')[0].replace('.', ' ').toUpperCase(),
          google_sub: `google_${email.replace(/[^a-zA-Z0-9]/g, '_')}`
        })
      });
      if (!res.ok) throw new Error('Login failed');
      const data = await res.json();
      setSessionToken(data.session_token);
      setCurrentUser(data.user);
      localStorage.setItem('session_token', data.session_token);
      localStorage.setItem('user_profile', JSON.stringify(data.user));
      setShowGoogleModal(false);
      setView('chat');
      loadThreads(data.session_token);
    } catch (err) {
      alert('Login error: ' + err.message);
    }
  };

  const logout = () => {
    localStorage.removeItem('session_token');
    localStorage.removeItem('user_profile');
    setSessionToken('');
    setCurrentUser(null);
    setCurrentThreadId('');
    setThreads([]);
    setMessages([]);
    setDemoSessionId('');
    setView('landing');
  };

  // Send message
  const handleSendMessage = async (e) => {
    if (e) e.preventDefault();
    const trimmed = inputMessage.trim();
    if (!trimmed || isProcessing) return;

    if (view === 'test_mode' && demoQueryCount >= DEMO_QUERY_LIMIT) {
      alert('You have reached the 5-question limit for Test Mode. Sign in to continue unlimited chatting!');
      return;
    }

    // Add user message immediately
    const userMsg = { role: 'user', content: trimmed };
    setMessages((prev) => [...prev, userMsg]);
    setInputMessage('');
    setIsProcessing(true);

    if (view === 'test_mode') {
      const newCount = demoQueryCount + 1;
      setDemoQueryCount(newCount);

      try {
        const response = await fetch(`${API_BASE}/chat/demo-stream`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            session_id: demoSessionId,
            message: trimmed,
            query_number: newCount
          })
        });

        if (!response.ok) throw new Error('Agent failed to process');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let aiText = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          aiText += decoder.decode(value, { stream: true });
        }

        setMessages((prev) => [...prev, { role: 'assistant', content: aiText }]);
      } catch (err) {
        setMessages((prev) => [
          ...prev, 
          { role: 'assistant', content: `⚠️ **Error:** ${err.message}. Please try again.` }
        ]);
      } finally {
        setIsProcessing(false);
      }
    } else {
      // Authenticated chat
      const threadIdToSend = currentThreadId || crypto.randomUUID();
      if (!currentThreadId) setCurrentThreadId(threadIdToSend);

      try {
        const response = await fetch(`${API_BASE}/chat/stream`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${sessionToken}`
          },
          body: JSON.stringify({
            thread_id: threadIdToSend,
            message: trimmed
          })
        });

        if (!response.ok) throw new Error('Agent request failed');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let aiText = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          aiText += decoder.decode(value, { stream: true });
        }

        setMessages((prev) => [...prev, { role: 'assistant', content: aiText }]);
        // Refresh threads to immediately reflect active agent change!
        loadThreads(sessionToken);
      } catch (err) {
        setMessages((prev) => [
          ...prev, 
          { role: 'assistant', content: `⚠️ **Error:** ${err.message}. Please try again.` }
        ]);
      } finally {
        setIsProcessing(false);
      }
    }
  };

  // Helper text for the timer (displayed after 5 seconds)
  const getTimerSubtext = (seconds) => {
    if (seconds <= 6) return 'Just a minute...';
    if (seconds <= 7) return 'Almost there...';
    if (seconds <= 8) return 'Almost there, querying database...';
    if (seconds <= 10) return 'Almost there, consulting specialist agent...';
    return 'Finalizing response...';
  };

  // Current active thread object
  const currentThreadObj = threads.find((t) => t.thread_id === currentThreadId);
  const currentAgentName = currentThreadObj ? currentThreadObj.agent_name : (view === 'test_mode' ? 'Demo Agent' : 'Support');
  const currentBadge = getAgentBadgeColor(currentAgentName);
  const CurrentBadgeIcon = currentBadge.icon;

  // ==========================================
  // VIEW: LANDING PAGE
  // ==========================================
  if (view === 'landing') {
    return (
      <div className="landing-hero">
        {/* Backend status indicator */}
        <div style={{
          position: 'absolute',
          top: '1.5rem',
          right: '2rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          fontSize: '0.85rem',
          padding: '0.4rem 0.8rem',
          borderRadius: '999px',
          background: 'rgba(18, 23, 33, 0.8)',
          border: '1px solid var(--border-color)',
          color: backendReady ? '#34d399' : '#f59e0b'
        }}>
          <div style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: backendReady ? '#10b981' : '#f59e0b',
            boxShadow: backendReady ? '0 0 8px #10b981' : 'none'
          }} />
          {checkingBackend ? 'Connecting to backend...' : (backendReady ? 'FastAPI Backend Online' : 'Backend Connecting')}
        </div>

        <div className="landing-card animate-fade-in">
          {/* Logo / Badge */}
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.4rem 0.9rem',
            borderRadius: '999px',
            background: 'var(--primary-glow)',
            border: '1px solid rgba(59, 130, 246, 0.3)',
            color: '#60a5fa',
            fontSize: '0.85rem',
            fontWeight: '600',
            marginBottom: '1.5rem'
          }}>
            <Sparkles size={16} /> LangGraph Multi-Agent Support System
          </div>

          <h1 style={{
            fontSize: '2.5rem',
            fontWeight: '700',
            letterSpacing: '-0.03em',
            marginBottom: '1rem',
            color: '#ffffff'
          }}>
            BrightCart Support AI
          </h1>

          <p style={{
            color: 'var(--text-secondary)',
            fontSize: '1.05rem',
            maxWidth: '560px',
            margin: '0 auto 2rem auto',
            lineHeight: 1.6
          }}>
            Autonomous multi-agent customer support platform built with <strong>LangGraph</strong> and <strong>FastAPI</strong>. Features dynamic supervisor routing across 5 specialist subgraphs, grounded <strong>Pinecone RAG</strong> for company policies, injection-safe database actions, and persistent thread memory.
          </p>

          {/* TWO REQUIRED BUTTONS */}
          <div className="landing-buttons">
            {/* Button 1: Sign in with Google */}
            <button 
              className="btn-secondary" 
              onClick={() => setShowGoogleModal(true)}
              style={{ padding: '1rem 1.5rem' }}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" style={{ marginRight: '4px' }}>
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
              </svg>
              Sign in with Google
            </button>

            {/* Button 2: Try Test Mode */}
            <button 
              className="btn-primary" 
              onClick={startTestMode}
              style={{ padding: '1rem 1.5rem' }}
            >
              <Sparkles size={18} />
              Try Test Mode
            </button>
          </div>

          <div style={{
            marginTop: '2rem',
            paddingTop: '1.5rem',
            borderTop: '1px solid var(--border-subtle)',
            display: 'flex',
            justifyContent: 'center',
            gap: '1.5rem',
            fontSize: '0.82rem',
            color: 'var(--text-muted)'
          }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <ShieldCheck size={14} color="#10b981" /> No login needed for Test Mode
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <CheckCircle2 size={14} color="#3b82f6" /> 0% Lag UI
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <Clock size={14} color="#f59e0b" /> 5-Query Recruiter Trial
            </span>
          </div>
        </div>

        {/* Google Login Dialog */}
        {showGoogleModal && (
          <div style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(6px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 100,
            padding: '1rem'
          }}>
            <div style={{
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '16px',
              maxWidth: '440px',
              width: '100%',
              padding: '2rem',
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)'
            }} className="animate-fade-in">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Sign in with Google</h3>
                <button 
                  onClick={() => setShowGoogleModal(false)}
                  style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                >
                  <X size={20} />
                </button>
              </div>

              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                Choose an option to sign in to BrightCart Support and unlock persistent chat history.
              </p>

              {/* Instant 1-click recruiter account */}
              <button
                className="btn-primary"
                onClick={() => handleGoogleLogin('recruiter.guest@brightcart.demo')}
                style={{ width: '100%', marginBottom: '1rem', justifyContent: 'center' }}
              >
                <User size={18} /> Continue as Recruiter Guest
              </button>

              <div style={{ display: 'flex', alignItems: 'center', margin: '1.25rem 0', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                <div style={{ flex: 1, height: '1px', background: 'var(--border-subtle)' }} />
                <span style={{ padding: '0 0.75rem' }}>OR CUSTOM EMAIL</span>
                <div style={{ flex: 1, height: '1px', background: 'var(--border-subtle)' }} />
              </div>

              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <input
                  type="email"
                  placeholder="Enter your email"
                  value={googleEmailInput}
                  onChange={(e) => setGoogleEmailInput(e.target.value)}
                  style={{
                    flex: 1,
                    background: 'var(--bg-tertiary)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '8px',
                    padding: '0.7rem 0.9rem',
                    color: '#fff',
                    fontSize: '0.9rem',
                    outline: 'none'
                  }}
                  onKeyDown={(e) => { if (e.key === 'Enter') handleGoogleLogin(); }}
                />
                <button
                  className="btn-secondary"
                  onClick={() => handleGoogleLogin()}
                  style={{ padding: '0.7rem 1.1rem' }}
                >
                  Sign In
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ==========================================
  // VIEW: CHAT INTERFACE (TEST MODE & AUTH MODE)
  // ==========================================
  return (
    <div className="app-container">
      {/* Mobile Drawer Overlay */}
      {sidebarOpen && (
        <div 
          onClick={() => setSidebarOpen(false)}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.6)',
            zIndex: 40
          }}
        />
      )}

      {/* LEFT SIDEBAR */}
      <aside style={{
        width: '300px',
        minWidth: '300px',
        background: 'var(--bg-secondary)',
        borderRight: '1px solid var(--border-color)',
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        zIndex: 50,
        position: window.innerWidth < 768 ? 'fixed' : 'relative',
        left: window.innerWidth < 768 ? (sidebarOpen ? 0 : '-300px') : 0,
        transition: 'left 0.25s ease'
      }}>
        {/* Sidebar Header */}
        <div style={{
          padding: '1.25rem 1rem',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div style={{
                background: 'var(--primary)',
                color: '#fff',
                padding: '0.35rem',
                borderRadius: '8px',
                display: 'flex'
              }}>
                <Bot size={18} />
              </div>
              <h2 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#fff' }}>BrightCart</h2>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
              {view === 'test_mode' ? 'Recruiter Test Mode' : (currentUser?.email || 'Logged in')}
            </div>
          </div>

          {window.innerWidth < 768 && (
            <button 
              onClick={() => setSidebarOpen(false)}
              style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
            >
              <X size={20} />
            </button>
          )}
        </div>

        {/* Action Button: New Chat or Test Info */}
        <div style={{ padding: '0.85rem 1rem' }}>
          {view === 'test_mode' ? (
            <div style={{
              background: 'rgba(59, 130, 246, 0.1)',
              border: '1px solid rgba(59, 130, 246, 0.3)',
              borderRadius: '8px',
              padding: '0.75rem',
              fontSize: '0.82rem'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#60a5fa', fontWeight: 600 }}>
                <span>Evaluation Queries</span>
                <span>{demoQueryCount}/{DEMO_QUERY_LIMIT}</span>
              </div>
              <div style={{
                height: '4px',
                background: 'var(--bg-tertiary)',
                borderRadius: '2px',
                marginTop: '0.5rem',
                overflow: 'hidden'
              }}>
                <div style={{
                  height: '100%',
                  width: `${(demoQueryCount / DEMO_QUERY_LIMIT) * 100}%`,
                  background: demoQueryCount >= DEMO_QUERY_LIMIT ? '#ef4444' : '#3b82f6',
                  transition: 'width 0.3s ease'
                }} />
              </div>
            </div>
          ) : (
            <button 
              className="btn-primary" 
              onClick={startNewChat}
              style={{ width: '100%', padding: '0.65rem 0.85rem', fontSize: '0.85rem' }}
            >
              <Plus size={16} /> New Chat
            </button>
          )}
        </div>

        {/* Sidebar Body */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '0.5rem 0.75rem'
        }}>
          {view === 'test_mode' ? (
            <div>
              <div style={{
                fontSize: '0.72rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
                letterSpacing: '0.05em',
                padding: '0.5rem 0.5rem 0.25rem 0.5rem'
              }}>
                Demo Customer Info
              </div>
              <div style={{
                background: 'var(--bg-tertiary)',
                borderRadius: '8px',
                padding: '0.75rem',
                border: '1px solid var(--border-subtle)',
                marginBottom: '1rem'
              }}>
                <div style={{ fontSize: '0.85rem', fontWeight: 600, color: '#fff' }}>Customer #{DEMO_USER_ID}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Recruiter Demo Profile</div>
              </div>

              <div style={{
                fontSize: '0.72rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
                letterSpacing: '0.05em',
                padding: '0.5rem 0.5rem 0.25rem 0.5rem'
              }}>
                Ordered Products
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {demoCustomer?.ordered_products?.length ? (
                  demoCustomer.ordered_products.map((p, idx) => (
                    <div 
                      key={idx} 
                      style={{
                        background: 'var(--bg-card)',
                        border: '1px solid var(--border-subtle)',
                        borderRadius: '8px',
                        padding: '0.6rem 0.75rem',
                        fontSize: '0.8rem'
                      }}
                    >
                      <div style={{ fontWeight: 600, color: '#e2e8f0' }}>{p.name}</div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '0.2rem' }}>
                        <span>Qty: {p.quantity}</span>
                        <span>₹{Number(p.price).toFixed(2)}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', padding: '0.5rem' }}>
                    Loading order catalog...
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div>
              <div style={{
                fontSize: '0.72rem',
                fontWeight: 600,
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
                letterSpacing: '0.05em',
                padding: '0.5rem 0.5rem 0.4rem 0.5rem'
              }}>
                My Conversations
              </div>

              {/* LIST OF CHATS SHOWING THE ACTIVE AGENT FIELD */}
              {/* As requested: if active agent is return_agent so in the left sidebar for that chat it should look like return */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                {threads.length === 0 ? (
                  <div style={{ fontSize: '0.82rem', color: 'var(--text-muted)', padding: '0.75rem' }}>
                    No conversations yet. Start a new chat!
                  </div>
                ) : (
                  threads.map((thread) => {
                    const agentLabel = formatAgentName(thread.active_agent || thread.agent_name);
                    const badge = getAgentBadgeColor(agentLabel);
                    const BadgeIcon = badge.icon;
                    const isSelected = thread.thread_id === currentThreadId;

                    return (
                      <button
                        key={thread.thread_id}
                        onClick={() => selectThread(thread.thread_id)}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.65rem',
                          padding: '0.65rem 0.75rem',
                          borderRadius: '8px',
                          border: isSelected ? '1px solid var(--primary)' : '1px solid transparent',
                          background: isSelected ? 'rgba(59, 130, 246, 0.12)' : 'transparent',
                          color: isSelected ? '#fff' : 'var(--text-secondary)',
                          cursor: 'pointer',
                          textAlign: 'left',
                          width: '100%',
                          transition: 'all 0.12s ease'
                        }}
                        onMouseEnter={(e) => {
                          if (!isSelected) e.currentTarget.style.background = 'var(--bg-hover)';
                        }}
                        onMouseLeave={(e) => {
                          if (!isSelected) e.currentTarget.style.background = 'transparent';
                        }}
                      >
                        {/* Agent Icon Badge */}
                        <div style={{
                          padding: '0.3rem',
                          borderRadius: '6px',
                          background: badge.bg,
                          color: badge.text,
                          border: `1px solid ${badge.border}`,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}>
                          <BadgeIcon size={14} />
                        </div>

                        {/* DISPLAY FIELD: Shows Active Agent (e.g. Return, Order, etc.) */}
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            fontSize: '0.88rem',
                            fontWeight: isSelected ? 600 : 500,
                            color: isSelected ? '#fff' : 'var(--text-primary)',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis'
                          }}>
                            {agentLabel}
                          </div>
                          <div style={{
                            fontSize: '0.72rem',
                            color: 'var(--text-muted)',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis'
                          }}>
                            {thread.thread_id.substring(0, 8)}...
                          </div>
                        </div>
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* Sidebar Footer */}
        <div style={{
          padding: '0.85rem 1rem',
          borderTop: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          {view === 'test_mode' ? (
            <button
              onClick={() => {
                setDemoSessionId('');
                setView('landing');
              }}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                background: 'none',
                border: 'none',
                color: 'var(--text-secondary)',
                fontSize: '0.85rem',
                cursor: 'pointer'
              }}
            >
              <LogOut size={16} /> Exit Test Mode
            </button>
          ) : (
            <button
              onClick={logout}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                background: 'none',
                border: 'none',
                color: 'var(--text-secondary)',
                fontSize: '0.85rem',
                cursor: 'pointer'
              }}
            >
              <LogOut size={16} /> Sign Out
            </button>
          )}

          <div style={{
            fontSize: '0.72rem',
            color: 'var(--text-muted)'
          }}>
            BrightCart v2.0
          </div>
        </div>
      </aside>

      {/* MAIN CHAT AREA */}
      <main style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        background: 'var(--bg-primary)',
        overflow: 'hidden',
        position: 'relative'
      }}>
        {/* Chat Top Navbar */}
        <header style={{
          height: '60px',
          borderBottom: '1px solid var(--border-color)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 1.25rem',
          background: 'rgba(18, 23, 33, 0.75)',
          backdropFilter: 'blur(8px)',
          zIndex: 10
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button
              onClick={() => setSidebarOpen(true)}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center'
              }}
            >
              <Menu size={20} />
            </button>

            {/* Active Agent Badge */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.3rem 0.75rem',
              borderRadius: '999px',
              background: currentBadge.bg,
              border: `1px solid ${currentBadge.border}`,
              color: currentBadge.text,
              fontSize: '0.8rem',
              fontWeight: 600
            }}>
              <CurrentBadgeIcon size={14} />
              <span>Active Agent: {currentAgentName}</span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {view === 'test_mode' ? (
              <span style={{
                background: 'rgba(245, 158, 11, 0.15)',
                color: '#fbbf24',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                padding: '0.25rem 0.65rem',
                borderRadius: '6px',
                fontSize: '0.75rem',
                fontWeight: 600
              }}>
                Recruiter Trial ({demoQueryCount}/{DEMO_QUERY_LIMIT})
              </span>
            ) : (
              <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                {currentUser?.name || 'Customer'}
              </span>
            )}
          </div>
        </header>

        {/* Message Feed */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          padding: '1.5rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '1.25rem'
        }}>
          {messages.length === 0 && (
            <div style={{
              margin: 'auto',
              textAlign: 'center',
              maxWidth: '480px',
              padding: '2rem'
            }}>
              <div style={{
                width: '48px',
                height: '48px',
                borderRadius: '12px',
                background: 'var(--primary-glow)',
                border: '1px solid rgba(59, 130, 246, 0.3)',
                color: '#60a5fa',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: '1rem'
              }}>
                <Bot size={24} />
              </div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: 600, color: '#fff', marginBottom: '0.5rem' }}>
                How can we assist you today?
              </h3>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
                Our autonomous agents can manage orders, process return requests, check item availability, and answer company policies.
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', textAlign: 'left' }}>
                {[
                  'Can I return the headphones from my order?',
                  'What is the status of my recent orders?',
                  'Do you have any active discount coupons?',
                  'What is your return policy for electronics?'
                ].map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => {
                      setInputMessage(prompt);
                    }}
                    style={{
                      background: 'var(--bg-card)',
                      border: '1px solid var(--border-color)',
                      borderRadius: '8px',
                      padding: '0.65rem 0.85rem',
                      color: 'var(--text-secondary)',
                      fontSize: '0.85rem',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.15s ease'
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.borderColor = '#3b82f6';
                      e.currentTarget.style.color = '#fff';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.borderColor = 'var(--border-color)';
                      e.currentTarget.style.color = 'var(--text-secondary)';
                    }}
                  >
                    💬 {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Render Chat Messages */}
          {messages.map((msg, index) => {
            const isUser = msg.role === 'user';
            return (
              <div 
                key={index} 
                style={{
                  display: 'flex',
                  gap: '0.75rem',
                  alignSelf: isUser ? 'flex-end' : 'flex-start',
                  maxWidth: isUser ? '75%' : '85%'
                }}
                className="animate-fade-in"
              >
                {!isUser && (
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    background: currentBadge.bg,
                    border: `1px solid ${currentBadge.border}`,
                    color: currentBadge.text,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    marginTop: '2px'
                  }}>
                    <CurrentBadgeIcon size={16} />
                  </div>
                )}

                <div style={{
                  background: isUser ? 'var(--user-bubble-bg)' : 'var(--ai-bubble-bg)',
                  border: isUser ? 'none' : '1px solid var(--border-color)',
                  borderRadius: isUser ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
                  padding: '0.85rem 1.15rem',
                  color: isUser ? '#fff' : 'var(--text-primary)',
                  boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)'
                }}>
                  {isUser ? (
                    <div style={{ fontSize: '0.95rem', whiteSpace: 'pre-wrap' }}>
                      {msg.content}
                    </div>
                  ) : (
                    <div 
                      className="prose"
                      dangerouslySetInnerHTML={{ __html: marked.parse(msg.content || '') }}
                    />
                  )}
                </div>

                {isUser && (
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    background: 'var(--bg-tertiary)',
                    border: '1px solid var(--border-color)',
                    color: '#60a5fa',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    marginTop: '2px'
                  }}>
                    <User size={16} />
                  </div>
                )}
              </div>
            );
          })}

          {/* AI PROCESSING & TIMER STATE */}
          {/* Requirement: whenever the user sends a message and while the ai agent processes that message show a small loading icon in front of the ai message box so that the user doesn't feel that the agent lagged and also if possible add a timer after 5 seconds like 6 7 8 9... in this manner and something written also comes up like just a min, almost there */}
          {isProcessing && (
            <div 
              style={{
                display: 'flex',
                gap: '0.75rem',
                alignSelf: 'flex-start',
                maxWidth: '85%'
              }}
              className="animate-fade-in"
            >
              {/* Small loading icon in front of the AI message box */}
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'rgba(59, 130, 246, 0.15)',
                border: '1px solid rgba(59, 130, 246, 0.3)',
                color: '#60a5fa',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
                marginTop: '2px'
              }}>
                <div style={{
                  width: '16px',
                  height: '16px',
                  border: '2px solid rgba(96, 165, 250, 0.2)',
                  borderTopColor: '#60a5fa',
                  borderRadius: '50%',
                  animation: 'spin 0.8s linear infinite'
                }} />
              </div>

              {/* AI Message Box showing loading and live timer */}
              <div style={{
                background: 'var(--ai-bubble-bg)',
                border: '1px solid var(--border-color)',
                borderRadius: '14px 14px 14px 2px',
                padding: '0.85rem 1.15rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.4rem',
                minWidth: '220px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  {/* Subtle pulsing dots */}
                  <div style={{ display: 'flex', gap: '3px' }}>
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#60a5fa', animation: 'bounceDots 1.2s infinite ease-in-out', animationDelay: '0s' }} />
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#60a5fa', animation: 'bounceDots 1.2s infinite ease-in-out', animationDelay: '0.2s' }} />
                    <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#60a5fa', animation: 'bounceDots 1.2s infinite ease-in-out', animationDelay: '0.4s' }} />
                  </div>

                  <span style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
                    {timerSeconds < 5 ? 'Thinking...' : 'Reasoning...'}
                  </span>
                </div>

                {/* TIMER AFTER 5 SECONDS (6, 7, 8, 9... with friendly text) */}
                {timerSeconds >= 5 && (
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    fontSize: '0.8rem',
                    color: '#fbbf24',
                    background: 'rgba(245, 158, 11, 0.1)',
                    padding: '0.25rem 0.5rem',
                    borderRadius: '6px',
                    border: '1px solid rgba(245, 158, 11, 0.25)',
                    marginTop: '0.2rem'
                  }} className="animate-fade-in">
                    <Clock size={13} className="animate-spin" />
                    <span><strong>{timerSeconds}s</strong> — {getTimerSubtext(timerSeconds)}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div style={{
          padding: '1rem 1.25rem',
          borderTop: '1px solid var(--border-color)',
          background: 'rgba(18, 23, 33, 0.75)',
          backdropFilter: 'blur(8px)'
        }}>
          <form 
            onSubmit={handleSendMessage}
            style={{
              display: 'flex',
              gap: '0.75rem',
              alignItems: 'center',
              background: 'var(--bg-secondary)',
              border: '1px solid var(--border-color)',
              borderRadius: '12px',
              padding: '0.4rem 0.6rem 0.4rem 1rem'
            }}
          >
            <input
              type="text"
              placeholder={
                view === 'test_mode' && demoQueryCount >= DEMO_QUERY_LIMIT
                  ? 'Demo question limit reached (5/5).'
                  : 'Type your message (e.g. Can I return my order?)...'
              }
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              disabled={isProcessing || (view === 'test_mode' && demoQueryCount >= DEMO_QUERY_LIMIT)}
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: '#fff',
                fontSize: '0.95rem',
                fontFamily: 'inherit'
              }}
            />

            <button
              type="submit"
              disabled={!inputMessage.trim() || isProcessing || (view === 'test_mode' && demoQueryCount >= DEMO_QUERY_LIMIT)}
              style={{
                background: inputMessage.trim() && !isProcessing ? 'var(--primary)' : 'var(--bg-tertiary)',
                color: inputMessage.trim() && !isProcessing ? '#fff' : 'var(--text-muted)',
                border: 'none',
                borderRadius: '8px',
                width: '36px',
                height: '36px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: inputMessage.trim() && !isProcessing ? 'pointer' : 'not-allowed',
                transition: 'all 0.15s ease'
              }}
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
