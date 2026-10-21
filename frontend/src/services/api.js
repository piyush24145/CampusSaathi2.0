
// API Base URL Resolution Priority:
// 1. User-customized URL from localStorage (useful for instant Vercel connection without redeploy)
// 2. Vite Environment Variable VITE_API_URL (configured in Vercel project settings)
// 3. Fallback to localhost if developing locally

export function getStoredBackendUrl() {
    if (typeof window !== "undefined") {
        return localStorage.getItem("CAMPUSSATHI_BACKEND_URL") || "";
    }
    return "";
}

export function setCustomApiBaseUrl(url) {
    if (typeof window !== "undefined") {
        if (!url || !url.trim()) {
            localStorage.removeItem("CAMPUSSATHI_BACKEND_URL");
        } else {
            const clean = url.trim().replace(/\/+$/, "");
            localStorage.setItem("CAMPUSSATHI_BACKEND_URL", clean);
        }
    }
}

export function getApiBaseUrl() {
    const stored = getStoredBackendUrl();
    if (stored) return stored.replace(/\/+$/, "");

    const envUrl = (import.meta.env.VITE_API_URL || "").trim();
    if (envUrl) return envUrl.replace(/\/+$/, "");

    if (typeof window !== "undefined") {
        const isLocal =
            window.location.hostname === "localhost" ||
            window.location.hostname === "127.0.0.1";
        if (isLocal) {
            return "http://localhost:8000";
        }
    }

    // Default to the user's Render backend URL if known, or empty
    return "https://campussaathi2-0.onrender.com";
}

/**
 * Universal fetch wrapper with configurable timeout (default 90s to handle Render free cold-starts)
 */
async function apiFetch(endpoint, options = {}, timeoutMs = 90000) {
    const baseUrl = getApiBaseUrl();
    if (!baseUrl) {
        throw new Error(
            "Backend URL is missing. Please configure your Render backend URL in the settings."
        );
    }

    const fullUrl = `${baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
    const controller = new AbortController();
    const timeoutTimer = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(fullUrl, {
            ...options,
            signal: controller.signal,
        });
        clearTimeout(timeoutTimer);
        return response;
    } catch (error) {
        clearTimeout(timeoutTimer);
        if (error.name === "AbortError") {
            throw new Error(
                "Request timed out. If your Render backend was sleeping (free tier spins down after inactivity), it takes ~45s to wake up. Please wait a moment and try again!"
            );
        }
        if (error.message && (error.message.includes("Failed to fetch") || error.message.includes("NetworkError"))) {
            throw new Error(
                `Cannot reach backend at ${baseUrl}. The server might be waking up on Render or the URL is incorrect.`
            );
        }
        throw error;
    }
}

/**
 * Fast ping to check if backend is online
 */
export async function checkBackendHealth() {
    try {
        const response = await apiFetch("/api/health", { method: "GET" }, 15000);
        if (response.ok) {
            return { online: true, url: getApiBaseUrl() };
        }
        return { online: false, url: getApiBaseUrl(), status: response.status };
    } catch (err) {
        return { online: false, url: getApiBaseUrl(), error: err.message };
    }
}

export async function askCampusSathi(question, filterSource = null) {
    const payload = {
        question: question.trim(),
        k: 4,
    };
    if (filterSource && filterSource.trim()) {
        payload.filter_source = filterSource.trim();
    }

    const response = await apiFetch("/api/ask", {
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

    const endpoint = `/api/documents/ingest?clear_previous=${clearPrevious ? "true" : "false"}`;
    // 120s timeout to allow large PDF parsing + embeddings generation + Render free-tier wake up
    const response = await apiFetch(endpoint, {
        method: "POST",
        body: formData,
    }, 120000);

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "PDF upload failed.");
    }

    return data;
}

export async function listCampusDocuments() {
    const response = await apiFetch("/api/documents", { method: "GET" }, 25000);
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || "Failed to load document list.");
    }
    return data.documents || [];
}

export async function deleteCampusDocument(filename) {
    const response = await apiFetch(
        `/api/documents/${encodeURIComponent(filename)}`,
        {
            method: "DELETE",
        },
        30000
    );
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || `Failed to delete ${filename}`);
    }
    return data;
}

export async function clearCampusDocuments() {
    const response = await apiFetch("/api/documents/clear", {
        method: "POST",
    }, 30000);

    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || "Failed to clear documents.");
    }
    return data;
}

/**
 * Transcribe recorded audio using Gnani STT API via backend.
 */
export async function transcribeAudio(audioBlob, language = "en-IN") {
    const formData = new FormData();
    formData.append("file", audioBlob, "recording.wav");
    formData.append("language", language);

    const response = await apiFetch("/api/voice/transcribe", {
        method: "POST",
        body: formData,
    }, 60000);

    const data = await response.json();

    if (!response.ok) {
        throw new Error(data.detail || "Failed to transcribe audio.");
    }

    return data;
}

/**
 * Convert text into speech using Gnani TTS API via backend.
 */
export async function speakText(text) {
    const cleanText = cleanTextForSpeech(text);

    if (!cleanText) {
        throw new Error("No readable text found to speak.");
    }

    const response = await apiFetch("/api/voice/speak", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            text: cleanText.slice(0, 2800),
        }),
    }, 60000);

    if (!response.ok) {
        let errorMsg = "Could not generate speech.";
        try {
            const errData = await response.json();
            errorMsg = errData.detail || errorMsg;
        } catch (_) {
            // fallback
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
        .replace(/```[\s\S]*?```/g, "Code block omitted.")
        .replace(/`([^`]+)`/g, "$1")
        .replace(/!\[.*?\]\(.*?\)/g, "")
        .replace(/\[(.*?)\]\(.*?\)/g, "$1")
        .replace(/[*_~#]/g, "")
        .replace(/^\s*[-+*]\s+/gm, "")
        .replace(/^\s*\d+\.\s+/gm, "")
        .replace(/\n+/g, " ")
        .trim();
}
