import { useState, useRef, useEffect } from "react";
import {
  askCampusSathi,
  uploadCampusDocument,
  listCampusDocuments,
  deleteCampusDocument,
  clearCampusDocuments,
  transcribeAudio,
  speakText,
  getApiBaseUrl,
  checkBackendHealth,
} from "./services/api";
import { AudioRecorder } from "./services/audioRecorder";
import ChatMessage from "./components/ChatMessage";
import VoiceRecorder from "./components/VoiceRecorder";
import AudioPlayer from "./components/AudioPlayer";
import "./App.css";

export default function App({ currentUser, onLogout }) {  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem("campusSathi_chatHistory");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [loading, setLoading] = useState(false);

  // Documents State (Phase 5 - Multiple Documents)
  const [documents, setDocuments] = useState([]);
  const [selectedDocFilter, setSelectedDocFilter] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  // Backend Connection Status
  const [backendStatus, setBackendStatus] = useState({ online: false, checking: true, url: "" });

  // Mobile Drawer State (Phase 6 - Mobile-friendly UI)
  const [isMobileDrawerOpen, setIsMobileDrawerOpen] = useState(false);

  // Voice States
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [voiceStatus, setVoiceStatus] = useState("");
  const [autoVoiceResponse, setAutoVoiceResponse] = useState(true);
  const [voiceLang, setVoiceLang] = useState("en-IN");
  const [recordDuration, setRecordDuration] = useState(0);

  // Audio Playback States
  const [playingIndex, setPlayingIndex] = useState(null);
  const [ttsLoadingIndex, setTtsLoadingIndex] = useState(null);
  const [currentlySpeakingSnippet, setCurrentlySpeakingSnippet] = useState("");

  const audioRecorderRef = useRef(null);
  const currentAudioRef = useRef(null);
  const recordingTimerRef = useRef(null);
  const isSpeakingRequestPendingRef = useRef(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Initial load: Fetch documents and init audio recorder
  useEffect(() => {
    audioRecorderRef.current = new AudioRecorder();
    verifyBackendAndLoad();

    return () => {
      stopAudioPlayback();
      if (audioRecorderRef.current) {
        audioRecorderRef.current.stop();
      }
      if (recordingTimerRef.current) {
        clearInterval(recordingTimerRef.current);
      }
    };
  }, []);

  async function verifyBackendAndLoad() {
    setBackendStatus({ online: false, checking: true, url: getApiBaseUrl() });
    const health = await checkBackendHealth();
    setBackendStatus({ online: health.online, checking: false, url: health.url, error: health.error });
    if (health.online) {
      loadDocuments();
    }
  }

  // Persist chat history to localStorage on every update
  useEffect(() => {
    try {
      localStorage.setItem("campusSathi_chatHistory", JSON.stringify(messages));
    } catch {
      // ignore quota errors
    }
  }, [messages]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function loadDocuments() {
    try {
      const docs = await listCampusDocuments();
      setDocuments(docs);
    } catch (err) {
      console.warn("Could not load documents list on startup:", err);
    }
  }

  function stopAudioPlayback() {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.src = "";
      currentAudioRef.current = null;
    }
    setPlayingIndex(null);
    setTtsLoadingIndex(null);
    setCurrentlySpeakingSnippet("");
  }

  // --------------------------------------------------
  // Submit Question (RAG with Citations & Multiple Docs)
  // --------------------------------------------------
  async function submitQuestion(textToSend, isFromVoice = false) {
    const text = (textToSend || question).trim();
    if (!text || loading) return;

    stopAudioPlayback();
    setErrorMessage("");

    setMessages((prev) => [
      ...prev,
      { role: "user", content: text, fromVoice: isFromVoice },
    ]);
    setQuestion("");
    setLoading(true);

    const targetAssistantIndex = messages.length + 1;

    try {
      const result = await askCampusSathi(text, selectedDocFilter);
      const newAnswer = result.answer;

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: newAnswer,
          sources: result.sources || [],
          is_answerable: result.is_answerable !== false,
          documents_available: result.documents_available || [],
        },
      ]);

      // Auto-speak if enabled or user asked via voice
      if (autoVoiceResponse || isFromVoice) {
        setTimeout(() => {
          playSpeech(targetAssistantIndex, newAnswer);
        }, 300);
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Unable to get answer: ${error.message}`,
          sources: [],
          is_answerable: false,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event) {
    event.preventDefault();
    submitQuestion(question, false);
  }

  // --------------------------------------------------
  // Voice Input (STT) & Anti-Duplication Helper
  // --------------------------------------------------
  const recognitionRef = useRef(null);
  const realtimeTextRef = useRef("");
  const finalTranscriptRef = useRef("");

  function deduplicateSpeech(text) {
    if (!text) return "";
    // 1. Remove consecutive identical words
    let words = text.trim().split(/\s+/);
    let deduped = [];
    for (let i = 0; i < words.length; i++) {
      if (i === 0 || words[i].toLowerCase() !== words[i - 1].toLowerCase()) {
        deduped.push(words[i]);
      }
    }

    // 2. Remove consecutive identical multi-word phrases (e.g. "give answer give answer")
    let changed = true;
    while (changed) {
      changed = false;
      const maxLen = Math.floor(deduped.length / 2);
      for (let len = maxLen; len >= 1; len--) {
        for (let i = 0; i <= deduped.length - 2 * len; i++) {
          const p1 = deduped.slice(i, i + len).join(" ").toLowerCase();
          const p2 = deduped.slice(i + len, i + 2 * len).join(" ").toLowerCase();
          if (p1 === p2) {
            deduped.splice(i + len, len);
            changed = true;
            break;
          }
        }
        if (changed) break;
      }
    }

    return deduped.join(" ");
  }

  async function handleToggleRecording() {
    stopAudioPlayback();
    setErrorMessage("");

    const SpeechRec =
      typeof window !== "undefined"
        ? window.SpeechRecognition || window.webkitSpeechRecognition
        : null;

    if (isRecording) {
      // User tapped Stop
      clearInterval(recordingTimerRef.current);

      if (SpeechRec && recognitionRef.current) {
        setVoiceStatus("Processing your speech...");
        try {
          recognitionRef.current.stop();
        } catch (_) {}
      } else {
        // Fallback for browsers without Web Speech API
        setIsRecording(false);
        setIsTranscribing(true);
        setVoiceStatus("Transcribing audio with Gnani STT...");
        try {
          const audioBlob = await audioRecorderRef.current.stop();
          if (audioBlob && audioBlob.size > 800) {
            const data = await transcribeAudio(audioBlob, voiceLang);
            const transcript = deduplicateSpeech(data.transcript?.trim() || "");
            if (transcript) {
              setVoiceStatus(`Recognized: "${transcript}"`);
              setQuestion(transcript);
              await submitQuestion(transcript, true);
              return;
            }
          }
          setVoiceStatus("No speech detected. Please speak closer to microphone.");
        } catch (err) {
          console.error("Transcription error:", err);
          setErrorMessage(`Voice transcription failed: ${err.message}`);
        } finally {
          setIsTranscribing(false);
          setTimeout(() => setVoiceStatus(""), 4000);
        }
      }
    } else {
      // User tapped Start Speaking
      realtimeTextRef.current = "";
      finalTranscriptRef.current = "";
      setRecordDuration(0);

      if (SpeechRec) {
        try {
          const recognition = new SpeechRec();
          // On mobile, continuous=true causes Android Chrome to emit duplicate looped buffers
          const isMobile = typeof navigator !== "undefined" && /Mobi|Android|iPhone/i.test(navigator.userAgent);
          recognition.continuous = !isMobile;
          recognition.interimResults = true;
          recognition.lang = voiceLang;

          recognition.onstart = () => {
            setIsRecording(true);
            setVoiceStatus(
              `Listening (${voiceLang === "hi-IN" ? "Hindi" : "English"})... Speak your question`
            );
          };

          recognition.onresult = (e) => {
            let interimTranscript = "";
            for (let i = e.resultIndex; i < e.results.length; i++) {
              const piece = e.results[i][0].transcript;
              if (e.results[i].isFinal) {
                finalTranscriptRef.current += " " + piece;
              } else {
                interimTranscript += " " + piece;
              }
            }

            const rawCombined = (finalTranscriptRef.current + " " + interimTranscript).trim();
            const clean = deduplicateSpeech(rawCombined);

            if (clean) {
              realtimeTextRef.current = clean;
              setQuestion(clean);
              setVoiceStatus(`Hearing: "${clean}"`);
            }
          };

          recognition.onerror = (e) => {
            console.warn("Speech recognition notice:", e.error);
            if (e.error === "not-allowed" || e.error === "permission-denied") {
              setErrorMessage(
                "Microphone access blocked. Please tap the lock/camera icon in your browser address bar to allow microphone access."
              );
              setIsRecording(false);
              clearInterval(recordingTimerRef.current);
            }
          };

          recognition.onend = () => {
            setIsRecording(false);
            clearInterval(recordingTimerRef.current);

            setTimeout(() => {
              const final = deduplicateSpeech(realtimeTextRef.current || finalTranscriptRef.current);
              if (final) {
                setQuestion(final);
                setVoiceStatus(`Recognized: "${final}"`);
                submitQuestion(final, true);
                setTimeout(() => setVoiceStatus(""), 4000);
              } else {
                setVoiceStatus("No speech detected. Tap mic to try again.");
                setTimeout(() => setVoiceStatus(""), 4000);
              }
            }, 250);
          };

          recognition.start();
          recognitionRef.current = recognition;
          setIsRecording(true);

          recordingTimerRef.current = setInterval(() => {
            setRecordDuration((prev) => prev + 1);
          }, 1000);
        } catch (err) {
          console.error("Failed to start SpeechRecognition:", err);
          setErrorMessage("Could not start microphone listener. Check browser permissions.");
        }
      } else {
        // Fallback for Firefox
        try {
          setVoiceStatus("Listening... Speak now");
          await audioRecorderRef.current.start();
          setIsRecording(true);
          recordingTimerRef.current = setInterval(() => {
            setRecordDuration((prev) => prev + 1);
          }, 1000);
        } catch (err) {
          console.error("Microphone access error:", err);
          setErrorMessage("Microphone access denied. Please grant permission in browser.");
          setIsRecording(false);
        }
      }
    }
  }

  // --------------------------------------------------
  // Voice Output (TTS)
  // --------------------------------------------------
  async function playSpeech(messageIndex, textContent) {
    if (isSpeakingRequestPendingRef.current) return;

    if (playingIndex === messageIndex) {
      stopAudioPlayback();
      return;
    }

    stopAudioPlayback();
    isSpeakingRequestPendingRef.current = true;
    setTtsLoadingIndex(messageIndex);
    setCurrentlySpeakingSnippet(textContent);

    try {
      const audioUrl = await speakText(textContent);
      const audio = new Audio(audioUrl);
      currentAudioRef.current = audio;

      audio.onplay = () => {
        setPlayingIndex(messageIndex);
        setTtsLoadingIndex(null);
      };

      audio.onended = () => {
        setPlayingIndex(null);
        setCurrentlySpeakingSnippet("");
        URL.revokeObjectURL(audioUrl);
      };

      audio.onerror = (e) => {
        console.error("Audio playback error:", e);
        setPlayingIndex(null);
        setTtsLoadingIndex(null);
        setCurrentlySpeakingSnippet("");
        URL.revokeObjectURL(audioUrl);
      };

      await audio.play();
    } catch (err) {
      console.error("TTS playback error:", err);
      setPlayingIndex(null);
      setTtsLoadingIndex(null);
      setCurrentlySpeakingSnippet("");
      setErrorMessage(`Voice generation note: ${err.message}`);
    } finally {
      isSpeakingRequestPendingRef.current = false;
    }
  }

  // --------------------------------------------------
  // Document Uploads (Multiple Documents Support)
  // --------------------------------------------------
  async function handleFileUpload(event) {
    const files = Array.from(event.target.files || []);
    event.target.value = "";
    if (files.length === 0) return;

    setUploading(true);
    setErrorMessage("");

    let successCount = 0;
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        if (!file.name.toLowerCase().endsWith(".pdf")) {
          setErrorMessage(`'${file.name}' is not a PDF. Only PDF files are supported.`);
          continue;
        }
        if (file.size > 15 * 1024 * 1024) {
          setErrorMessage(`'${file.name}' exceeds the 15 MB size limit.`);
          continue;
        }

        setUploadStatus(
          `Indexing [${i + 1}/${files.length}]: ${file.name}... (Extracting text & computing embeddings)`
        );

        try {
          await uploadCampusDocument(file, false);
          successCount++;
        } catch (err) {
          console.error("Upload error:", err);
          setErrorMessage(`Failed to upload '${file.name}': ${err.message}`);
        }
      }

      // Refresh documents list
      await loadDocuments();
    } finally {
      setUploading(false);
      if (successCount > 0) {
        setUploadStatus(`✓ Successfully indexed ${successCount} notice(s)!`);
        setTimeout(() => setUploadStatus(""), 4500);
      } else {
        setUploadStatus("");
      }
    }
  }

  async function handleDeleteDocument(filename) {
    if (!window.confirm(`Are you sure you want to remove '${filename}'?`)) return;
    try {
      await deleteCampusDocument(filename);
      await loadDocuments();
      if (selectedDocFilter === filename) {
        setSelectedDocFilter(null);
      }
      setUploadStatus(`✓ Removed '${filename}'.`);
      setTimeout(() => setUploadStatus(""), 3500);
    } catch (err) {
      setErrorMessage(`Could not remove document: ${err.message}`);
    }
  }

  async function handleClearAllDocuments() {
    if (documents.length === 0) return;
    if (!window.confirm("Remove ALL uploaded notices from the system?")) return;

    try {
      await clearCampusDocuments();
      await loadDocuments();
      setSelectedDocFilter(null);
      setUploadStatus("✓ All documents cleared.");
      setTimeout(() => setUploadStatus(""), 3500);
    } catch (err) {
      setErrorMessage(`Failed to clear documents: ${err.message}`);
    }
  }

  return (
    <div className="app-shell">
      {/* Mobile Drawer Overlay */}
      {isMobileDrawerOpen && (
        <div
          className="drawer-overlay"
          onClick={() => setIsMobileDrawerOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar (Desktop) & Slide-in Drawer (Mobile) */}
      <aside className={`sidebar ${isMobileDrawerOpen ? "drawer-open" : ""}`}>
        <div className="sidebar-header">
          <div className="brand">
            <div className="brand-icon">CS</div>
            <div>
              <h2>CampusSathi</h2>
              <span>AI College Assistant</span>
            </div>
          </div>
          {/* Close button inside mobile drawer */}
          <button
            type="button"
            className="drawer-close-btn"
            onClick={() => setIsMobileDrawerOpen(false)}
            aria-label="Close menu"
          >
            ✕
          </button>
        </div>

        <button
          className="new-chat-btn"
          onClick={() => {
            stopAudioPlayback();
            setMessages([]);
            localStorage.removeItem("campusSathi_chatHistory");
            setIsMobileDrawerOpen(false);
          }}
        >
          <span>+</span> New Conversation
        </button>

        {/* Document Management Section */}
        <div className="sidebar-doc-section">
          <div className="doc-section-title">
            <span>COLLEGE NOTICES ({documents.length})</span>
            {documents.length > 0 && (
              <button
                type="button"
                className="clear-all-link"
                onClick={handleClearAllDocuments}
                title="Remove all uploaded notices"
              >
                Clear all
              </button>
            )}
          </div>

          {/* Quick Filter: All vs Specific Notice */}
          {documents.length > 1 && (
            <div className="filter-pill-container">
              <button
                type="button"
                className={`filter-pill ${selectedDocFilter === null ? "active" : ""}`}
                onClick={() => {
                  setSelectedDocFilter(null);
                  setIsMobileDrawerOpen(false);
                }}
              >
                All Notices
              </button>
              {documents.map((d) => (
                <button
                  key={d.filename}
                  type="button"
                  className={`filter-pill ${selectedDocFilter === d.filename ? "active" : ""}`}
                  onClick={() => {
                    setSelectedDocFilter(
                      selectedDocFilter === d.filename ? null : d.filename
                    );
                    setIsMobileDrawerOpen(false);
                  }}
                  title={`Focus questions exclusively on ${d.filename}`}
                >
                  {d.filename.replace(".pdf", "").slice(0, 16)}...
                </button>
              ))}
            </div>
          )}

          {/* Document list */}
          <div className="sidebar-doc-list">
            {documents.length === 0 ? (
              <div className="no-docs-hint">
                <span className="no-docs-icon">📄</span>
                <p>No college notices uploaded yet.</p>
                <small>Upload multiple exam, hostel, or library notices (PDF) to ask questions!</small>
              </div>
            ) : (
              documents.map((doc) => (
                <div
                  className={`doc-card-item ${
                    selectedDocFilter === doc.filename ? "selected" : ""
                  }`}
                  key={doc.filename}
                  onClick={() => {
                    setSelectedDocFilter(
                      selectedDocFilter === doc.filename ? null : doc.filename
                    );
                    setIsMobileDrawerOpen(false);
                  }}
                >
                  <div className="doc-card-left">
                    <span className="doc-pdf-emoji">📄</span>
                    <div className="doc-card-details">
                      <strong className="doc-card-name" title={doc.filename}>
                        {doc.filename}
                      </strong>
                      <span className="doc-card-meta">
                        {doc.total_pages} {doc.total_pages === 1 ? "page" : "pages"} · {doc.total_chunks} chunks
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    className="delete-doc-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteDocument(doc.filename);
                    }}
                    title={`Delete ${doc.filename}`}
                    aria-label={`Delete ${doc.filename}`}
                  >
                    🗑️
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Upload Button in Sidebar (Multiple PDFs supported) */}
          <label className={`sidebar-upload-btn ${uploading ? "uploading" : ""}`}>
            {uploading ? (
              <>
                <span className="spinner-small" />
                <span>Processing PDF(s)...</span>
              </>
            ) : (
              <>
                <span>{documents.length > 0 ? "+ Add More Notices (PDF)" : "↑ Upload Notices (PDF)"}</span>
              </>
            )}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              multiple
              onChange={handleFileUpload}
              disabled={uploading}
              hidden
            />
          </label>
        </div>

        {/* Sidebar Settings (Voice Mode) */}
        <div className="sidebar-section">
          <div className="voice-mode-card">
            <div className="voice-mode-header">
              <span className="voice-icon">🎙️</span>
              <div>
                <strong>Auto-Read Answers</strong>
                <p>Reads AI responses aloud with voice</p>
              </div>
            </div>
            <button
              type="button"
              className={`toggle-btn ${autoVoiceResponse ? "active" : ""}`}
              onClick={() => setAutoVoiceResponse(!autoVoiceResponse)}
            >
              {autoVoiceResponse ? "ON" : "OFF"}
            </button>
          </div>
        </div>

        {/* User Profile & Logout inside Sidebar (Especially great for Mobile Drawer) */}
        <div className="sidebar-user-card">
          <div className="sidebar-user-avatar">
            {currentUser?.picture ? (
              <img src={currentUser.picture} alt="" className="avatar-img" />
            ) : (
              <span>{(currentUser?.name || "U")[0].toUpperCase()}</span>
            )}
          </div>
          <div className="sidebar-user-info">
            <span className="sidebar-user-name" title={currentUser?.name}>
              {currentUser?.name || "Student"}
            </span>
            <span className="sidebar-user-email" title={currentUser?.email}>
              {currentUser?.email || ""}
            </span>
          </div>
          <button
            type="button"
            className="sidebar-logout-btn"
            title="Log out"
            onClick={() => {
              stopAudioPlayback();
              onLogout();
            }}
          >
            🚪 Logout
          </button>
        </div>

        <div className="sidebar-footer">
          CampusSathi AI — Grounded answers with exact citations and multi-notice support.
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="chat-area">
        {/* Top Header with Mobile Drawer Hamburger */}
        <header className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="mobile-hamburger-btn"
              onClick={() => setIsMobileDrawerOpen(true)}
              aria-label="Open navigation drawer"
            >
              <span className="hamburger-line" />
              <span className="hamburger-line" />
              <span className="hamburger-line" />
            </button>

            <div className="topbar-branding">
              <div className="title-row">
                <h1>CampusSathi AI</h1>
                <span className="doc-count-badge">
                  {documents.length > 0
                    ? `📚 ${documents.length} ${documents.length === 1 ? "Notice" : "Notices"}`
                    : "📄 No Notices"}
                </span>
              </div>
              <p className="topbar-subtitle">
                Ask about college notices via text or voice with citations
              </p>
            </div>
          </div>

          <div className="topbar-actions">
            <div className={`server-status-pill ${backendStatus.online ? "online" : backendStatus.checking ? "checking" : "offline"}`} title={backendStatus.online ? "Backend connected" : "Backend offline"}>
              <span className={`status-indicator-dot ${backendStatus.online ? "online" : backendStatus.checking ? "checking" : "offline"}`} />
              <span className="server-status-text">
                {backendStatus.checking ? "Connecting..." : backendStatus.online ? "🟢 AI Ready" : "🔴 Offline"}
              </span>
            </div>

            <button
              type="button"
              className={`voice-toggle-topbar ${autoVoiceResponse ? "enabled" : ""}`}
              onClick={() => setAutoVoiceResponse(!autoVoiceResponse)}
              title="Toggle automatic speech playback for answers"
            >
              <span className="speaker-icon">
                {autoVoiceResponse ? "🔊" : "🔇"}
              </span>
              <span className="voice-toggle-text">
                Auto-Read: {autoVoiceResponse ? "ON" : "OFF"}
              </span>
            </button>

            {/* User info + Logout */}
            <div className="topbar-user">
              <span className="topbar-user-avatar">
                {currentUser?.picture ? (
                  <img src={currentUser.picture} alt="" className="avatar-img" />
                ) : (
                  <span>{(currentUser?.name || "U")[0].toUpperCase()}</span>
                )}
              </span>
              <span className="topbar-user-name">{currentUser?.name || "User"}</span>
              <button
                type="button"
                className="logout-btn"
                title="Log out"
                onClick={() => {
                  stopAudioPlayback();
                  onLogout();
                }}
              >
                Logout
              </button>
            </div>
          </div>
        </header>

        {/* Global Error Banner */}
        {errorMessage && (
          <div className="error-banner" role="alert">
            <span className="error-icon">⚠️</span>
            <span className="error-text">{errorMessage}</span>
            <button
              type="button"
              className="error-dismiss"
              onClick={() => setErrorMessage("")}
              aria-label="Dismiss error"
            >
              ✕
            </button>
          </div>
        )}

        {/* Global Upload Banner */}
        {uploadStatus && (
          <div className="upload-banner" role="status">
            <span className="upload-icon">ℹ️</span>
            <span>{uploadStatus}</span>
          </div>
        )}

        {/* Active Filter Notice Badge */}
        {selectedDocFilter && (
          <div className="active-filter-bar">
            <span>Filter active: Querying only <strong>{selectedDocFilter}</strong></span>
            <button
              type="button"
              className="clear-filter-btn"
              onClick={() => setSelectedDocFilter(null)}
            >
              Reset to All Notices ✕
            </button>
          </div>
        )}

        {/* Conversation Area */}
        <section className="conversation">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-hero-badge">
                <span className="sparkle-icon">✦</span> Campus Assistant
              </div>
              <h2 className="welcome-title">Campus notices, answered instantly.</h2>
              <p className="welcome-desc">
                Ask questions about your college circulars using <strong>Voice (Hindi / English)</strong> or <strong>Text</strong>. Every response is verified with exact PDF source citations and page numbers.
              </p>

              {/* Quick Notice Upload Zone if empty, or Notice Ready Status */}
              {documents.length === 0 ? (
                <div
                  className="welcome-upload-dropzone"
                  onClick={() => fileInputRef.current?.click()}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => e.key === "Enter" && fileInputRef.current?.click()}
                >
                  <div className="dropzone-icon-box">
                    <svg className="dropzone-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="17 8 12 3 7 8" />
                      <line x1="12" y1="3" x2="12" y2="15" />
                    </svg>
                  </div>
                  <div className="dropzone-info">
                    <strong>Click to Upload College Notices (PDF)</strong>
                    <p>Select exam circulars, fee schedules, hostel rules, or library guidelines</p>
                  </div>
                  <span className="dropzone-btn-pill">Select PDFs</span>
                </div>
              ) : (
                <div className="welcome-ready-card">
                  <div className="ready-card-badge">
                    <span>📚</span>
                    <strong>{documents.length} {documents.length === 1 ? "Notice" : "Notices"} Loaded & Indexed</strong>
                  </div>
                  <p>Type your question below or tap the microphone to ask in Hindi or English.</p>
                </div>
              )}

              {/* Key Features Triplet */}
              <div className="welcome-features-grid">
                <div className="feature-pill-card">
                  <span className="feature-emoji">🎙️</span>
                  <div>
                    <strong>Bilingual Voice</strong>
                    <p>Hindi & English speech recognition</p>
                  </div>
                </div>
                <div className="feature-pill-card">
                  <span className="feature-emoji">📑</span>
                  <div>
                    <strong>Exact Citations</strong>
                    <p>Verified with page numbers</p>
                  </div>
                </div>
                <div className="feature-pill-card">
                  <span className="feature-emoji">⚡</span>
                  <div>
                    <strong>Multi-Notice RAG</strong>
                    <p>Answers across all documents</p>
                  </div>
                </div>
              </div>

              {/* Voice CTA Button */}
              <div className="welcome-voice-cta">
                <button
                  type="button"
                  className="hero-mic-button"
                  onClick={handleToggleRecording}
                  disabled={loading || isTranscribing}
                >
                  <span className="hero-mic-icon">🎙️</span>
                  <span>Tap to Speak Question ({voiceLang === "hi-IN" ? "Hindi" : "English"})</span>
                </button>
              </div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((message, index) => (
                <ChatMessage
                  key={`${index}-${message.role}`}
                  message={message}
                  index={index}
                  isPlaying={playingIndex === index}
                  isTtsLoading={ttsLoadingIndex === index}
                  onPlaySpeech={() => playSpeech(index, message.content)}
                />
              ))}

              {loading && (
                <div className="loading-message">
                  <span className="spinner" />
                  <span>Searching notices & generating reliable answer with citations...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </section>

        {/* Live Voice Status Floating Strip */}
        {(voiceStatus || isRecording || isTranscribing) && (
          <div className={`voice-banner ${isRecording ? "recording" : ""}`}>
            {isRecording ? (
              <div className="recording-status-box">
                <span className="recording-pulse-dot" />
                <span className="recording-timer">{recordDuration}s</span>
                <span className="recording-hint">Listening to your voice... Speak now or tap mic to finish</span>
              </div>
            ) : isTranscribing ? (
              <div className="transcribing-status-box">
                <span className="spinner-small" />
                <span>Transcribing your speech with Gnani AI...</span>
              </div>
            ) : (
              <span>{voiceStatus}</span>
            )}
          </div>
        )}

        {/* Persistent Floating Audio Player (Active when TTS plays) */}
        <AudioPlayer
          isPlaying={playingIndex !== null}
          onStop={stopAudioPlayback}
          textSnippet={currentlySpeakingSnippet}
        />

        {/* Unified Chat Composer at Bottom */}
        <div className="composer-container">
          <form className="composer-card" onSubmit={handleSubmit}>
            <textarea
              className="composer-textarea"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing
                ) {
                  event.preventDefault();
                  event.currentTarget.form.requestSubmit();
                }
              }}
              placeholder={
                isRecording
                  ? "Listening to your voice... Speak your question..."
                  : documents.length === 0
                  ? "Upload college notices (PDF) to start asking questions..."
                  : `Ask anything across ${
                      selectedDocFilter
                        ? selectedDocFilter
                        : `${documents.length} uploaded notice${documents.length === 1 ? "" : "s"}`
                    }...`
              }
              rows={1}
              disabled={loading || isTranscribing}
            />

            <div className="composer-actions-bar">
              {/* Left Context Notice Badge */}
              <div className="composer-context-pill">
                {documents.length > 0 ? (
                  <span className="context-chip active" title={selectedDocFilter || `${documents.length} notices`}>
                    <span className="chip-icon">📄</span>
                    <span className="chip-text">
                      {selectedDocFilter ? selectedDocFilter.replace(".pdf", "") : `${documents.length} ${documents.length === 1 ? "notice" : "notices"}`}
                    </span>
                  </span>
                ) : (
                  <span className="context-chip empty">
                    <span className="chip-icon">⚠️</span>
                    <span className="chip-text">No notice uploaded</span>
                  </span>
                )}
              </div>

              {/* Right Controls & Send Button */}
              <div className="composer-buttons-group">
                <VoiceRecorder
                  isRecording={isRecording}
                  isTranscribing={isTranscribing}
                  recordDuration={recordDuration}
                  voiceLang={voiceLang}
                  onToggleRecording={handleToggleRecording}
                  onToggleLang={() =>
                    setVoiceLang(voiceLang === "en-IN" ? "hi-IN" : "en-IN")
                  }
                  disabled={loading}
                />

                <button
                  type="submit"
                  className={`composer-send-btn ${question.trim() ? "has-text" : ""}`}
                  disabled={loading || !question.trim() || isRecording || isTranscribing}
                  title="Send question (Enter)"
                  aria-label="Send question"
                >
                  {loading ? (
                    <span className="spinner-small" />
                  ) : (
                    <svg className="send-svg-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="12" y1="19" x2="12" y2="5" />
                      <polyline points="5 12 12 5 19 12" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
          </form>

          <div className="composer-footer-disclaimer">
            <span>CampusSathi answers are verified against uploaded notices. Always cross-check critical dates with original college circulars.</span>
          </div>
        </div>
      </main>

    </div>
  );
}