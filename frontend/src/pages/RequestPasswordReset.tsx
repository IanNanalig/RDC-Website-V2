import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../config/api";
import TurnstileWidget from "../components/TurnstileWidget";

const RequestPasswordReset: React.FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [captchaToken, setCaptchaToken] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const hasCaptcha = Boolean(import.meta.env.VITE_TURNSTILE_SITE_KEY);

  const goBack = () => {
    if (Number(window.history.state?.idx) > 0) {
      navigate(-1);
    } else {
      navigate("/login");
    }
  };

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
      const normalizedEmail = email.trim().toLowerCase();
      const res = await fetch(`${API_BASE_URL}/auth/password-reset/request/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: normalizedEmail,
          captcha_token: captchaToken || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Failed to send the reset code.");
      }
      setNotice(data?.detail || "If this email is registered, a reset code has been sent.");
      navigate("/reset-password", { state: { email: normalizedEmail } });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to send the reset code.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-8 sm:px-6">
      <div className="w-full max-w-md space-y-5 rounded-2xl border border-slate-200 bg-white p-5 shadow-lg sm:p-7">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Request Password Reset</h1>
        <p className="text-sm leading-relaxed text-slate-600">
          Enter your email and we will send a six-digit reset code. The code expires in 10 minutes.
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

        <form onSubmit={onSubmit} className="space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-slate-700">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-slate-900 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-200"
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
            className="portal-btn portal-btn-primary min-h-11 w-full disabled:cursor-wait disabled:opacity-60"
          >
            {loading ? "Sending code..." : "Send Reset Code"}
          </button>
        </form>

        <button type="button" onClick={goBack} className="portal-btn portal-btn-ghost min-h-10">
          <span aria-hidden="true">←</span> Back
        </button>
      </div>
    </div>
  );
};

export default RequestPasswordReset;
