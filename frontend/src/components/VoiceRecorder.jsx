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
          <span className="mic-svg-icon" aria-hidden="true">🎙️</span>
        )}

        <span className="mic-text-tag">
          {isTranscribing ? "Wait" : isRecording ? "Stop" : "Mic"}
        </span>
      </button>
    </div>
  );
}
