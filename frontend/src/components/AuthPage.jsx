import { useState, useEffect, useRef } from "react";
import { registerUser, loginUser, googleLogin } from "../services/api";
import "./AuthPage.css";

const GOOGLE_CLIENT_ID =
  (import.meta.env.VITE_GOOGLE_CLIENT_ID || "").trim() ||
  "546909821073-k7pr94rn2tsc7rok6fbbauu85dm3tg24.apps.googleusercontent.com";

export default function AuthPage({ onAuthSuccess }) {
  const [mode, setMode] = useState("login"); // "login" | "register"
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState("");

  const googleBtnRef = useRef(null);

  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    college: "",
  });

  function handleChange(e) {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
    setError("");
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      let data;
      if (mode === "login") {
        data = await loginUser({ email: form.email, password: form.password });
      } else {
        if (!form.name.trim()) return setError("Please enter your name.");
        if (form.password.length < 6) return setError("Password must be at least 6 characters.");
        data = await registerUser({
          name: form.name,
          email: form.email,
          password: form.password,
          college: form.college,
        });
      }
      onAuthSuccess(data.user);
    } catch (err) {
      setError(err.message || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogleSuccess(credential) {
    setGoogleLoading(true);
    setError("");
    try {
      const data = await googleLogin(credential);
      onAuthSuccess(data.user);
    } catch (err) {
      setError(err.message || "Google login failed. Please try again.");
    } finally {
      setGoogleLoading(false);
    }
  }

  // Setup Google Identity Services button if Client ID exists
  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || !googleBtnRef.current) return;

    const setupGoogle = () => {
      if (window.google?.accounts?.id) {
        try {
          window.google.accounts.id.initialize({
            client_id: GOOGLE_CLIENT_ID,
            callback: (res) => {
              if (res && res.credential) {
                handleGoogleSuccess(res.credential);
              }
            },
          });

          if (googleBtnRef.current) {
            googleBtnRef.current.innerHTML = "";
            window.google.accounts.id.renderButton(googleBtnRef.current, {
              theme: "filled_black",
              size: "large",
              text: mode === "login" ? "signin_with" : "signup_with",
              shape: "rectangular",
              width: 320,
            });
          }
        } catch (err) {
          console.warn("Google Sign-In initialization failed:", err);
        }
      }
    };

    if (window.google?.accounts?.id) {
      setupGoogle();
    } else {
      const interval = setInterval(() => {
        if (window.google?.accounts?.id) {
          clearInterval(interval);
          setupGoogle();
        }
      }, 300);
      return () => clearInterval(interval);
    }
  }, [mode]);

  return (
    <div className="auth-page">
      {/* Background decoration */}
      <div className="auth-bg-circle auth-bg-circle--1" />
      <div className="auth-bg-circle auth-bg-circle--2" />

      <div className="auth-card">
        {/* Logo / Header */}
        <div className="auth-header">
          <div className="auth-logo">🎓</div>
          <h1 className="auth-title">CampusSathi</h1>
          <p className="auth-subtitle">
            {mode === "login"
              ? "Welcome back! Log in to continue."
              : "Create your account to get started."}
          </p>
        </div>

        {/* Tab switcher */}
        <div className="auth-tabs">
          <button
            className={`auth-tab ${mode === "login" ? "active" : ""}`}
            onClick={() => { setMode("login"); setError(""); }}
            type="button"
          >
            Log In
          </button>
          <button
            className={`auth-tab ${mode === "register" ? "active" : ""}`}
            onClick={() => { setMode("register"); setError(""); }}
            type="button"
          >
            Register
          </button>
        </div>

        {/* Form */}
        <form className="auth-form" onSubmit={handleSubmit}>
          {mode === "register" && (
            <div className="auth-field">
              <label>Full Name</label>
              <input
                type="text"
                name="name"
                placeholder="Rahul Sharma"
                value={form.name}
                onChange={handleChange}
                required
                autoComplete="name"
              />
            </div>
          )}

          <div className="auth-field">
            <label>Email</label>
            <input
              type="email"
              name="email"
              placeholder="you@college.edu"
              value={form.email}
              onChange={handleChange}
              required
              autoComplete="email"
            />
          </div>

          <div className="auth-field">
            <label>Password</label>
            <input
              type="password"
              name="password"
              placeholder={mode === "register" ? "Min 6 characters" : "Your password"}
              value={form.password}
              onChange={handleChange}
              required
              autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
          </div>

          {mode === "register" && (
            <div className="auth-field">
              <label>College Name <span className="optional">(optional)</span></label>
              <input
                type="text"
                name="college"
                placeholder="e.g. IIT Delhi, VIT Vellore..."
                value={form.college}
                onChange={handleChange}
                autoComplete="organization"
              />
            </div>
          )}

          {error && (
            <div className="auth-error">
              <span>⚠️</span> {error}
            </div>
          )}

          <button
            type="submit"
            className="auth-submit-btn"
            disabled={loading}
          >
            {loading
              ? (mode === "login" ? "Logging in..." : "Creating account...")
              : (mode === "login" ? "🚀 Log In" : "✨ Create Account")}
          </button>
        </form>

        {/* Google OAuth Divider */}
        {GOOGLE_CLIENT_ID && (
          <>
            <div className="auth-divider">
              <span>or</span>
            </div>

            <div className="google-btn-wrapper">
              <div ref={googleBtnRef} />
            </div>

            {googleLoading && (
              <p className="google-loading">Verifying Google account...</p>
            )}
          </>
        )}

        {/* Switch mode link */}
        <p className="auth-switch">
          {mode === "login" ? (
            <>Don't have an account?{" "}
              <button type="button" onClick={() => { setMode("register"); setError(""); }}>
                Register here
              </button>
            </>
          ) : (
            <>Already have an account?{" "}
              <button type="button" onClick={() => { setMode("login"); setError(""); }}>
                Log in
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
