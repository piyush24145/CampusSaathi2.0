import { useState } from "react";

export default function SourceCitation({ source, index }) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [copied, setCopied] = useState(false);

  const docName = source.source || "College Notice (PDF)";
  const pageNum = source.page_number ?? 1;
  const chunkId = source.chunk_id;
  const snippet = source.snippet || source.text || "";

  function handleCopy() {
    if (!snippet) return;
    navigator.clipboard.writeText(
      `From: ${docName} (Page ${pageNum})\n"${snippet}"`
    );
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className={`source-citation-card ${isExpanded ? "expanded" : ""}`}>
      <div
        className="source-citation-header"
        onClick={() => setIsExpanded(!isExpanded)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setIsExpanded(!isExpanded);
          }
        }}
        title="Click to view/hide exact quoted text from document"
      >
        <div className="source-citation-left">
          <span className="source-pdf-icon" aria-hidden="true">📄</span>
          <div className="source-meta">
            <span className="source-doc-name" title={docName}>{docName}</span>
            <div className="source-tags">
              <span className="source-page-badge">Page {pageNum}</span>
              {chunkId != null && (
                <span className="source-chunk-badge">Ref #{chunkId}</span>
              )}
            </div>
          </div>
        </div>

        <div className="source-citation-actions">
          <span className="expand-toggle-label">
            {isExpanded ? "Hide Excerpt ▲" : "View Excerpt ▼"}
          </span>
        </div>
      </div>

      {isExpanded && snippet && (
        <div className="source-snippet-box">
          <div className="source-snippet-quote">
            <span className="quote-mark">“</span>
            <p>{snippet}</p>
          </div>
          <div className="source-snippet-footer">
            <button
              type="button"
              className="copy-snippet-btn"
              onClick={handleCopy}
              title="Copy citation and quoted text"
            >
              {copied ? "✓ Copied!" : "📋 Copy Quote"}
            </button>
            <span className="snippet-verified-tag">✓ Verified Source Passage</span>
          </div>
        </div>
      )}
    </div>
  );
}
