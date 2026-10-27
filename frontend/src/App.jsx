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
  setCustomApiBaseUrl,
  checkBackendHealth,
} from "./services/api";
import { AudioRecorder } from "./services/audioRecorder";
import ChatMessage from "./components/ChatMessage";
import VoiceRecorder from "./components/VoiceRecorder";
import AudioPlayer from "./components/AudioPlayer";
import "./App.css";

export default function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  // Documents State (Phase 5 - Multiple Documents)
  const [documents, setDocuments] = useState([]);
  const [selectedDocFilter, setSelectedDocFilter] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  // Backend Connection & Settings Modal
  const [backendStatus, setBackendStatus] = useState({ online: false, checking: true, url: "" });
  const [showServerModal, setShowServerModal] = useState(false);
  const [serverUrlInput, setServerUrlInput] = useState("");
  const [testResult, setTestResult] = useState(null);
  const [isTesting, setIsTesting] = useState(false);

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

  async function testBackendUrl() {
    setIsTesting(true);
    setTestResult(null);
    try {
      const urlToTest = (serverUrlInput || getApiBaseUrl()).trim().replace(/\/+$/, "");
      const res = await fetch(`${urlToTest}/api/health`, { method: "GET", signal: AbortSignal.timeout(15000) });
      if (res.ok) {
        setTestResult({ success: true, message: "Connected successfully! Backend is online." });
      } else {
        setTestResult({ success: false, message: `Server replied with status ${res.status}.` });
      }
    } catch (err) {
      setTestResult({
        success: false,
        message: err.name === "TimeoutError" 
          ? "Request timed out. If Render is waking up from sleep, wait ~45s." 
          : `Connection error: ${err.message}`,
      });
    } finally {
      setIsTesting(false);
    }
  }

  function saveBackendUrl() {
    if (serverUrlInput && serverUrlInput.trim()) {
      setCustomApiBaseUrl(serverUrlInput.trim());
    }
    setShowServerModal(false);
    verifyBackendAndLoad();
  }

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
  // Voice Input (STT)
  // --------------------------------------------------
  const recognitionRef = useRef(null);
  const realtimeTextRef = useRef("");

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
            const transcript = data.transcript?.trim() || "";
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
      setRecordDuration(0);

      if (SpeechRec) {
        try {
          const recognition = new SpeechRec();
          recognition.continuous = true;
          recognition.interimResults = true;
          recognition.lang = voiceLang;

          recognition.onstart = () => {
            setIsRecording(true);
            setVoiceStatus(
              `Listening (${voiceLang === "hi-IN" ? "Hindi" : "English"})... Speak your question`
            );
          };

          recognition.onresult = (e) => {
            let transcript = "";
            for (let i = 0; i < e.results.length; i++) {
              transcript += e.results[i][0].transcript + " ";
            }
            const clean = transcript.trim();
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
              const final = realtimeTextRef.current.trim();
              if (final) {
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
  // Document Uploads (Phase 5 - Multi-Document Support)
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
          setUploadStatus("");
          setErrorMessage(`Failed to upload '${file.name}': ${err.message}`);
        }
      }

      // Refresh active documents list
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
            setIsMobileDrawerOpen(false);
          }}
        >
          <span>+</span> New Conversation
        </button>

        {/* Document Management Section (Phase 5) */}
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
                onClick={() => setSelectedDocFilter(null)}
              >
                All Notices
              </button>
              {documents.map((d) => (
                <button
                  key={d.filename}
                  type="button"
                  className={`filter-pill ${selectedDocFilter === d.filename ? "active" : ""}`}
                  onClick={() =>
                    setSelectedDocFilter(
                      selectedDocFilter === d.filename ? null : d.filename
                    )
                  }
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
                <small>Upload multiple exam, hostel, or library notices to ask questions!</small>
              </div>
            ) : (
              documents.map((doc) => (
                <div
                  className={`doc-card-item ${
                    selectedDocFilter === doc.filename ? "selected" : ""
                  }`}
                  key={doc.filename}
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

          {/* Upload Button in Sidebar */}
          <label className={`sidebar-upload-btn ${uploading ? "uploading" : ""}`}>
            {uploading ? (
              <>
                <span className="spinner-small" />
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <span>↑ Upload Notices (PDF)</span>
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

            <div>
              <div className="title-row">
                <h1>CampusSathi AI</h1>
                <span className="doc-count-badge">
                  📚 {documents.length} {documents.length === 1 ? "Notice" : "Notices"}
                </span>
              </div>
              <p className="topbar-subtitle">
                Ask about college notices via text or voice with source citations
              </p>
            </div>
          </div>

          <div className="topbar-actions">
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
              <div className="welcome-icon">CS</div>
              <h2>Campus notices, answered instantly.</h2>
              <p>
                Ask questions about your college circulars using{" "}
                <strong>Voice (Hindi / English)</strong> or <strong>Text</strong>.
                Each answer includes exact PDF source citations and page numbers.
              </p>

              {/* Hero Action for Voice */}
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

              {/* Quick suggestions based on uploaded notices */}
              <div className="suggestions-wrapper">
                <span className="suggestions-title">TRY ASKING:</span>
                <div className="suggestions">
                  {[
                    "When do the semester examinations start and what is the fee?",
                    "What is the hostel curfew time and total fee?",
                    "How many books can a student borrow from the library?",
                    "What is the Sunday mess menu?",
                  ].map((item) => (
                    <button
                      key={item}
                      type="button"
                      onClick={() => submitQuestion(item, false)}
                    >
                      <span>{item}</span>
                      <span className="arrow-icon">↗</span>
                    </button>
                  ))}
                </div>
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
                <span className="recording-hint">Listening... Speak now or tap mic to finish</span>
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

        {/* Chat Composer Fixed at Bottom */}
        <form className="composer" onSubmit={handleSubmit}>
          <div className="composer-input-row">
            <textarea
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
                  ? "Upload a college notice (PDF) to start asking questions..."
                  : `Ask a question across ${
                      selectedDocFilter
                        ? selectedDocFilter
                        : `${documents.length} uploaded notices`
                    }...`
              }
              rows={2}
              disabled={loading || isTranscribing}
            />

            {/* Voice Recorder Control */}
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
          </div>

          <div className="composer-bottom">
            <div className="composer-hint">
              {documents.length > 0 ? (
                <span>
                  Searching:{" "}
                  <strong>
                    {selectedDocFilter || `${documents.length} notices`}
                  </strong>
                </span>
              ) : (
                <span>No notice uploaded yet</span>
              )}
            </div>

            <button
              type="submit"
              className="send-button"
              disabled={
                loading || !question.trim() || isRecording || isTranscribing
              }
            >
              {loading ? (
                <>
                  <span className="spinner-small" />
                  <span>Thinking...</span>
                </>
              ) : (
                <>
                  <span>Ask AI</span>
                  <span className="send-arrow">↑</span>
                </>
              )}
            </button>
          </div>
        </form>

        <footer className="disclaimer">
          CampusSathi answers are verified against uploaded notices. Always cross-check critical dates with original college circulars.
        </footer>
      </main>
    </div>
  );
}

