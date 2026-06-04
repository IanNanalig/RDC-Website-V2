import React, { useState } from "react";
import { Link } from "react-router-dom";
import { API_BASE_URL } from "../config/api";
import TurnstileWidget from "../components/TurnstileWidget";

const RequestPasswordReset: React.FC = () => {
  const [email, setEmail] = useState("");
  const [captchaToken, setCaptchaToken] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const hasCaptcha = Boolean(import.meta.env.VITE_TURNSTILE_SITE_KEY);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice("");
    setError("");
    if (!email.trim()) {
      setError("Email is required.");
      return;
    }
    if (hasCaptcha && !captchaToken) {
      setError("Please complete the captcha before submitting.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/password-reset-requests/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          captcha_token: captchaToken || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Failed to send reset request.");
      }
      setNotice(
        "If this email is registered, your request has been sent to the administrator. You will receive a reset link once approved.",
      );
      setEmail("");
      setCaptchaToken("");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to send reset request.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-md bg-white rounded-xl shadow-lg border border-slate-200 p-6 space-y-4">
        <h1 className="text-2xl font-semibold text-slate-900">Request Password Reset</h1>
        <p className="text-sm text-slate-600">
          Enter your email to request a password reset. An administrator will review the request.
        </p>

        {notice && (
          <div className="p-3 rounded bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm">
            {notice}
          </div>
        )}
        {error && (
          <div className="p-3 rounded bg-rose-50 border border-rose-200 text-rose-700 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-3">
          <label className="block">
            <span className="text-sm text-slate-700">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full border rounded-lg px-3 py-2"
              autoComplete="email"
              required
            />
          </label>

          {hasCaptcha && (
            <div className="pt-1">
              <TurnstileWidget onToken={setCaptchaToken} />
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full portal-btn portal-btn-primary"
          >
            {loading ? "Sending..." : "Send Reset Request"}
          </button>
        </form>

        <div className="text-xs text-slate-500">
          Back to <Link to="/login" className="text-blue-600 hover:underline">login</Link>
        </div>
      </div>
    </div>
  );
};

export default RequestPasswordReset;
