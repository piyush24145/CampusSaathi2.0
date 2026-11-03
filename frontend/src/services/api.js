
// API Base URL Resolution Priority:
// 1. Vite Environment Variable VITE_API_URL (configured in project settings)
// 2. Fallback to localhost if developing locally

export function getApiBaseUrl() {
    const envUrl = (import.meta.env.VITE_API_URL || "").trim();
    if (envUrl) return envUrl.replace(/\/+$/, "");

    if (typeof window !== "undefined") {
        const isLocal =
            window.location.hostname === "localhost" ||
            window.location.hostname === "127.0.0.1";
        if (isLocal) return "http://localhost:8000";
    }
    return "";
}

// ---------------------------------------------------------------------------
// Auth token helpers (JWT stored in localStorage)
// ---------------------------------------------------------------------------

export function getAuthToken() {
    return localStorage.getItem("campusSathi_token") || null;
}

export function saveAuthToken(token) {
    localStorage.setItem("campusSathi_token", token);
}

export function saveCurrentUser(user) {
    localStorage.setItem("campusSathi_user", JSON.stringify(user));
}

export function getCurrentUser() {
    try {
        const raw = localStorage.getItem("campusSathi_user");
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

export function clearAuth() {
    localStorage.removeItem("campusSathi_token");
    localStorage.removeItem("campusSathi_user");
    localStorage.removeItem("campusSathi_chatHistory");
}

export function isLoggedIn() {
    return !!getAuthToken();
}

// ---------------------------------------------------------------------------
// Universal fetch wrapper — auto-attaches JWT
// ---------------------------------------------------------------------------

async function apiFetch(endpoint, options = {}, timeoutMs = 60000) {
    const baseUrl = getApiBaseUrl();
    if (!baseUrl) {
        throw new Error("Backend URL is not configured.");
    }

    const token = getAuthToken();
    const headers = { ...(options.headers || {}) };
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    const fullUrl = `${baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
    const controller = new AbortController();
    const timeoutTimer = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const response = await fetch(fullUrl, { ...options, headers, signal: controller.signal });
        clearTimeout(timeoutTimer);

        // Auto-logout on 401
        if (response.status === 401) {
            clearAuth();
            window.location.href = "/";
        }

        return response;
    } catch (error) {
        clearTimeout(timeoutTimer);
        if (error.name === "AbortError") {
            throw new Error("Request timed out. Please verify that your backend server is active.");
        }
        if (error.message?.includes("Failed to fetch") || error.message?.includes("NetworkError")) {
            throw new Error(`Cannot reach backend at ${baseUrl}. Check your network and server status.`);
        }
        throw error;
    }
}

// ---------------------------------------------------------------------------
// Health check
// ---------------------------------------------------------------------------

export async function checkBackendHealth() {
    try {
        const response = await apiFetch("/api/health", { method: "GET" }, 15000);
        if (response.ok) return { online: true, url: getApiBaseUrl() };
        return { online: false, url: getApiBaseUrl(), status: response.status };
    } catch (err) {
        return { online: false, url: getApiBaseUrl(), error: err.message };
    }
}

// ---------------------------------------------------------------------------
// Auth API calls
// ---------------------------------------------------------------------------

export async function registerUser({ name, email, password, college }) {
    const response = await apiFetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password, college }),
    }, 20000);

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Registration failed.");

    saveAuthToken(data.access_token);
    saveCurrentUser(data.user);
    return data;
}

export async function loginUser({ email, password }) {
    const response = await apiFetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
    }, 20000);

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Login failed.");

    saveAuthToken(data.access_token);
    saveCurrentUser(data.user);
    return data;
}

export async function googleLogin(credential) {
    const response = await apiFetch("/api/auth/google", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ credential }),
    }, 20000);

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Google login failed.");

    saveAuthToken(data.access_token);
    saveCurrentUser(data.user);
    return data;
}

export async function fetchCurrentUser() {
    const response = await apiFetch("/api/auth/me", { method: "GET" }, 10000);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not fetch user.");
    return data.user;
}

// ---------------------------------------------------------------------------
// Document & RAG API calls (all protected, JWT auto-attached)
// ---------------------------------------------------------------------------

export async function askCampusSathi(question, filterSource = null) {
    const payload = { question: question.trim(), k: 4 };
    if (filterSource?.trim()) payload.filter_source = filterSource.trim();

    const response = await apiFetch(
        "/api/ask",
        {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        },
        120000
    );

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Could not get an answer.");
    return data;
}

export async function uploadCampusDocument(file, clearPrevious = false) {
    const formData = new FormData();
    formData.append("file", file);

    const response = await apiFetch(
        `/api/documents/ingest?clear_previous=${clearPrevious ? "true" : "false"}`,
        { method: "POST", body: formData },
        120000
    );

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "PDF upload failed.");
    return data;
}

export async function listCampusDocuments() {
    const response = await apiFetch("/api/documents", { method: "GET" }, 25000);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Failed to load document list.");
    return data.documents || [];
}

export async function deleteCampusDocument(filename) {
    const response = await apiFetch(
        `/api/documents/${encodeURIComponent(filename)}`,
        { method: "DELETE" },
        30000
    );
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Failed to delete ${filename}`);
    return data;
}

export async function clearCampusDocuments() {
    const response = await apiFetch("/api/documents/clear", { method: "POST" }, 30000);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Failed to clear documents.");
    return data;
}

// ---------------------------------------------------------------------------
// Voice API calls
// ---------------------------------------------------------------------------

export async function transcribeAudio(audioBlob, language = "en-IN") {
    const formData = new FormData();
    formData.append("file", audioBlob, "recording.wav");
    formData.append("language", language);

    const response = await apiFetch("/api/voice/transcribe", {
        method: "POST",
        body: formData,
    }, 60000);

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Failed to transcribe audio.");
    return data;
}

export async function speakText(text) {
    const cleanText = cleanTextForSpeech(text);
    if (!cleanText) throw new Error("No readable text found to speak.");

    const response = await apiFetch("/api/voice/speak", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: cleanText.slice(0, 2800) }),
    }, 60000);

    if (!response.ok) {
        let errorMsg = "Could not generate speech.";
        try { const e = await response.json(); errorMsg = e.detail || errorMsg; } catch (_) {}
        throw new Error(errorMsg);
    }

    const audioBlob = await response.blob();
    return URL.createObjectURL(audioBlob);
}

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
