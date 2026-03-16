import React, { useMemo, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { API_BASE_URL } from "../config/api";

const passwordRules = [
  { label: "At least 12 characters", test: (v: string) => v.length >= 12 },
  { label: "At least 1 uppercase letter", test: (v: string) => /[A-Z]/.test(v) },
  { label: "At least 1 lowercase letter", test: (v: string) => /[a-z]/.test(v) },
  { label: "At least 1 number", test: (v: string) => /[0-9]/.test(v) },
  { label: "At least 1 symbol", test: (v: string) => /[\W_]/.test(v) },
];

const validatePassword = (value: string) => {
  if (value.length < 12) return "Password must be at least 12 characters.";
  if (!/[A-Z]/.test(value)) return "Password must include an uppercase letter.";
  if (!/[a-z]/.test(value)) return "Password must include a lowercase letter.";
  if (!/[0-9]/.test(value)) return "Password must include a number.";
  if (!/[\W_]/.test(value)) return "Password must include a symbol.";
  return "";
};

const SetupPassword: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  const policyError = useMemo(() => validatePassword(password), [password]);
  const confirmError = useMemo(
    () => (confirm && password !== confirm ? "Passwords do not match." : ""),
    [password, confirm],
  );

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!token) {
      setError("Missing setup token. Please use the link from your email.");
      return;
    }
    if (policyError) {
      setError(policyError);
      return;
    }
    if (confirmError) {
      setError(confirmError);
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/setup-password/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Failed to set password.");
      }
      setSuccess("Password set successfully. You can now log in.");
      setTimeout(() => navigate("/login", { replace: true }), 1500);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to set password.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-md bg-white rounded-xl shadow-lg border border-slate-200 p-6 space-y-4">
        <h1 className="text-2xl font-semibold text-slate-900">Set Your Password</h1>
        <p className="text-sm text-slate-600">
          Use the secure link sent to your email. This link is valid for 24 hours.
        </p>

        {!token && (
          <div className="p-3 rounded bg-amber-50 border border-amber-200 text-amber-800 text-sm">
            Missing setup token. Please use the link from your email.
          </div>
        )}

        {error && (
          <div className="p-3 rounded bg-rose-50 border border-rose-200 text-rose-700 text-sm">
            {error}
          </div>
        )}
        {success && (
          <div className="p-3 rounded bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm">
            {success}
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-3">
          <label className="block">
            <span className="text-sm text-slate-700">New Password</span>
            <div className="relative mt-1">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 pr-10"
                autoComplete="new-password"
                required
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? (
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 3l18 18" />
                    <path d="M10.58 10.58A3 3 0 0012 15a3 3 0 002.42-4.42" />
                    <path d="M9.88 5.08A10.94 10.94 0 0112 5c4.5 0 8.25 3 9.5 7a12.4 12.4 0 01-2.07 3.22" />
                    <path d="M6.18 6.18A12.4 12.4 0 002.5 12c1.25 4 5 7 9.5 7 1.4 0 2.74-.27 3.98-.77" />
                  </svg>
                ) : (
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M2.5 12c1.25-4 5-7 9.5-7s8.25 3 9.5 7c-1.25 4-5 7-9.5 7s-8.25-3-9.5-7z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </label>
          <label className="block">
            <span className="text-sm text-slate-700">Confirm Password</span>
            <div className="relative mt-1">
              <input
                type={showConfirm ? "text" : "password"}
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                className="w-full border rounded-lg px-3 py-2 pr-10"
                autoComplete="new-password"
                required
              />
              <button
                type="button"
                onClick={() => setShowConfirm((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-700"
                aria-label={showConfirm ? "Hide password" : "Show password"}
              >
                {showConfirm ? (
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M3 3l18 18" />
                    <path d="M10.58 10.58A3 3 0 0012 15a3 3 0 002.42-4.42" />
                    <path d="M9.88 5.08A10.94 10.94 0 0112 5c4.5 0 8.25 3 9.5 7a12.4 12.4 0 01-2.07 3.22" />
                    <path d="M6.18 6.18A12.4 12.4 0 002.5 12c1.25 4 5 7 9.5 7 1.4 0 2.74-.27 3.98-.77" />
                  </svg>
                ) : (
                  <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M2.5 12c1.25-4 5-7 9.5-7s8.25 3 9.5 7c-1.25 4-5 7-9.5 7s-8.25-3-9.5-7z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
          </label>

          <div className="text-xs text-slate-600 space-y-1">
            <div className="font-semibold text-slate-700">Password rules:</div>
            <ul className="space-y-1">
              {passwordRules.map((rule) => {
                const ok = rule.test(password);
                return (
                  <li key={rule.label} className={`flex items-center gap-2 ${ok ? "text-emerald-600" : "text-slate-500"}`}>
                    <span
                      className={`inline-flex h-4 w-4 items-center justify-center rounded-full border ${
                        ok ? "border-emerald-500 bg-emerald-100 text-emerald-700" : "border-slate-300 text-slate-400"
                      }`}
                    >
                      {ok ? "✓" : "•"}
                    </span>
                    <span>{rule.label}</span>
                  </li>
                );
              })}
            </ul>
          </div>

          <button
            type="submit"
            disabled={loading || Boolean(policyError) || Boolean(confirmError) || !token}
            className="w-full portal-btn portal-btn-primary"
          >
            {loading ? "Saving..." : "Set Password"}
          </button>
        </form>

        <div className="text-xs text-slate-500">
          Need help? <Link to="/login" className="text-blue-600 hover:underline">Back to login</Link>
        </div>
      </div>
    </div>
  );
};

export default SetupPassword;
