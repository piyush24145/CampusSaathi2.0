import ReactMarkdown from "react-markdown";
import SourceCitation from "./SourceCitation";
import { useState } from "react";

export default function ChatMessage({
  message,
  index,
  isPlaying,
  isTtsLoading,
  onPlaySpeech,
}) {
  const [copiedAnswer, setCopiedAnswer] = useState(false);
  const isAssistant = message.role === "assistant";

  function handleCopyAnswer() {
    navigator.clipboard.writeText(message.content);
    setCopiedAnswer(true);
    setTimeout(() => setCopiedAnswer(false), 2000);
  }

  return (
    <article className={`message ${message.role}`}>
      <div className="avatar">
        {isAssistant ? "✦" : "You"}
      </div>

      <div className="message-body">
        <div className="message-header">
          <span className="author-name">
            {isAssistant ? "CampusSathi AI" : "You"}
          </span>

          {message.fromVoice && (
            <span className="voice-badge">
              🎙️ Voice Input
            </span>
          )}

          {isAssistant && message.is_answerable === false && (
            <span className="unanswerable-tag">
              ⚠️ Not in Documents
            </span>
          )}

          {isAssistant && (
            <div className="message-actions-row">
              <button
                type="button"
                className="copy-answer-btn"
                onClick={handleCopyAnswer}
                title="Copy entire answer text"
              >
                {copiedAnswer ? "✓ Copied" : "Copy"}
              </button>

              <button
                type="button"
                className={`listen-button ${
                  isPlaying ? "playing" : isTtsLoading ? "loading" : ""
                }`}
                onClick={onPlaySpeech}
                title={isPlaying ? "Stop listening" : "Listen to answer aloud"}
              >
                {isTtsLoading ? (
                  <>
                    <span className="spinner-small" />
                    <span className="listen-btn-text">Generating voice...</span>
                  </>
                ) : isPlaying ? (
                  <>
                    <span className="equalizer-bars">
                      <span className="bar bar-1" />
                      <span className="bar bar-2" />
                      <span className="bar bar-3" />
                    </span>
                    <span className="listen-btn-text">Stop speaking</span>
                  </>
                ) : (
                  <>
                    <span className="speak-icon">🔊</span>
                    <span className="listen-btn-text">Listen</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        {/* Unanswerable / Out of Domain Guidance Card */}
        {isAssistant && message.is_answerable === false && (
          <div className="unanswerable-notice-card">
            <div className="notice-icon">ℹ️</div>
            <div className="notice-content">
              <strong>Notice Content Not Found</strong>
              <p>
                The uploaded documents do not contain direct answers to this question. Please verify your query or upload the corresponding notice PDF.
              </p>
            </div>
          </div>
        )}

        <div className="message-text">
          <ReactMarkdown>{message.content}</ReactMarkdown>
        </div>

        {/* Source Citations with exact PDF names, pages, and expandable quotes */}
        {message.sources && message.sources.length > 0 && (
          <div className="sources-container">
            <div className="sources-header">
              <span className="sources-title">
                📚 Source Citations ({message.sources.length})
              </span>
              <span className="sources-sub">
                Grounded strictly in your uploaded college notices
              </span>
            </div>

            <div className="sources-list">
              {message.sources.map((source, sIdx) => (
                <SourceCitation
                  key={`${source.source}-${source.page_number}-${source.chunk_id}-${sIdx}`}
                  source={source}
                  index={sIdx}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </article>
  );
}
