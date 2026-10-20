export default function AudioPlayer({ isPlaying, onStop, textSnippet }) {
  if (!isPlaying) return null;

  return (
    <div className="persistent-audio-player" role="region" aria-label="Audio playback">
      <div className="audio-player-left">
        <div className="audio-wave-anim">
          <span className="wave-bar wb-1" />
          <span className="wave-bar wb-2" />
          <span className="wave-bar wb-3" />
          <span className="wave-bar wb-4" />
        </div>
        <div className="audio-player-info">
          <strong>Speaking Answer</strong>
          <span className="audio-snippet-preview">
            {textSnippet ? `"${textSnippet.slice(0, 45)}..."` : "Playing speech audio"}
          </span>
        </div>
      </div>

      <button
        type="button"
        className="audio-stop-btn"
        onClick={onStop}
        title="Stop audio playback"
      >
        <span className="audio-stop-icon">■</span>
        <span>Stop</span>
      </button>
    </div>
  );
}
