export default function VoiceRecorder({
  isRecording,
  isTranscribing,
  recordDuration,
  voiceLang,
  onToggleRecording,
  onToggleLang,
  disabled,
}) {
  const formatDuration = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  return (
    <div className="voice-recorder-control">
      <button
        type="button"
        className="voice-lang-pill"
        onClick={onToggleLang}
        disabled={isRecording || disabled}
        title="Switch between English and Hindi voice input"
      >
        <span className="lang-flag">{voiceLang === "hi-IN" ? "🇮🇳" : "🌐"}</span>
        <span className="lang-name">{voiceLang === "hi-IN" ? "Hindi" : "English"}</span>
      </button>

      <button
        type="button"
        className={`voice-mic-main-btn ${isRecording ? "recording" : ""} ${
          isTranscribing ? "transcribing" : ""
        }`}
        onClick={onToggleRecording}
        disabled={disabled || isTranscribing}
        aria-label={isRecording ? "Stop voice recording" : "Start speaking question"}
        title={
          isRecording
            ? "Click or tap to stop recording"
            : `Tap to speak question in ${voiceLang === "hi-IN" ? "Hindi" : "English"}`
        }
      >
        {isTranscribing ? (
          <span className="spinner-small" />
        ) : isRecording ? (
          <div className="mic-stop-container">
            <span className="mic-stop-square" />
            <span className="mic-duration-badge">{formatDuration(recordDuration)}</span>
          </div>
        ) : (
          <svg className="mic-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="22" />
          </svg>
        )}
      </button>
    </div>
  );
}
