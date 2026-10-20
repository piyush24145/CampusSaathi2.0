
// Uses VITE_API_URL in production, or same-origin Vite proxy on dev server
const API_BASE_URL =
    import.meta.env.VITE_API_URL ||
    (typeof window !== "undefined" && (window.location.port === "5173" || window.location.port === "5174")
        ? ""
        : (typeof window !== "undefined" && window.location.hostname === "localhost"
            ? "http://localhost:8000"
            : "http://127.0.0.1:8000"));

export async function askCampusSathi(question, filterSource = null) {
    const payload = {
        question: question.trim(),
        k: 4,
    };
    if (filterSource && filterSource.trim()) {
        payload.filter_source = filterSource.trim();
    }

    const response = await fetch(`${API_BASE_URL}/api/ask`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Could not get an answer.");
    }

    return data;
}

export async function uploadCampusDocument(file, clearPrevious = false) {
    const formData = new FormData();
    formData.append("file", file);

    const url = `${API_BASE_URL}/api/documents/ingest?clear_previous=${clearPrevious ? "true" : "false"}`;
    const response = await fetch(url, {
        method: "POST",
        body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "PDF upload failed.");
    }

    return data;
}

export async function listCampusDocuments() {
    const response = await fetch(`${API_BASE_URL}/api/documents`);
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || "Failed to load document list.");
    }
    return data.documents || [];
}

export async function deleteCampusDocument(filename) {
    const response = await fetch(
        `${API_BASE_URL}/api/documents/${encodeURIComponent(filename)}`,
        {
            method: "DELETE",
        }
    );
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || `Failed to delete ${filename}`);
    }
    return data;
}

export async function clearCampusDocuments() {
    const response = await fetch(`${API_BASE_URL}/api/documents/clear`, {
        method: "POST",
    });

    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || "Failed to clear documents.");
    }
    return data;
}

/**
 * Transcribe recorded audio using Gnani STT API via backend.
 * @param {Blob} audioBlob - The recorded audio blob (WAV format)
 * @returns {Promise<{success: boolean, transcript: string}>}
 */
export async function transcribeAudio(audioBlob, language = "en-IN") {
    const formData = new FormData();
    formData.append("file", audioBlob, "recording.wav");
    formData.append("language", language);

    const response = await fetch(`${API_BASE_URL}/api/voice/transcribe`, {
        method: "POST",
        body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Failed to transcribe audio.");
    }

    return data;
}

/**
 * Convert text into speech using Gnani TTS API via backend.
 * @param {string} text - The text to synthesize
 * @returns {Promise<string>} - Object URL pointing to the WAV audio
 */
export async function speakText(text) {
    const cleanText = cleanTextForSpeech(text);

    if (!cleanText) {
        throw new Error("No readable text found to speak.");
    }

    const response = await fetch(`${API_BASE_URL}/api/voice/speak`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            text: cleanText.slice(0, 2800), // Gnani limit is 3000 chars
        }),
    });

    if (!response.ok) {
        let errorMsg = "Could not generate speech.";
        try {
            const errData = await response.json();
            errorMsg = errData.detail || errorMsg;
        } catch (_) {
            // fallback if not json
        }
        throw new Error(errorMsg);
    }

    const audioBlob = await response.blob();
    return URL.createObjectURL(audioBlob);
}

/**
 * Strips markdown symbols, code blocks, links, and formatting
 * so TTS reads text naturally and smoothly.
 */
export function cleanTextForSpeech(markdownText) {
    if (!markdownText) return "";
    return markdownText
        .replace(/```[\s\S]*?```/g, "Code block omitted.") // Code blocks
        .replace(/`([^`]+)`/g, "$1") // Inline code
        .replace(/!\[.*?\]\(.*?\)/g, "") // Images
        .replace(/\[(.*?)\]\(.*?\)/g, "$1") // Links -> link text only
        .replace(/[*_~#]/g, "") // Bold, italics, headers
        .replace(/^\s*[-+*]\s+/gm, "") // List bullets
        .replace(/^\s*\d+\.\s+/gm, "") // Numbered lists
        .replace(/\n+/g, " ") // Collapse newlines
        .trim();
}
