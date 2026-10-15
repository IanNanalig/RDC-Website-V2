import React, { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { API_BASE_URL } from "../config/api";
import { passwordRules, validatePassword } from "../utils/passwordPolicy";

const ResetPassword: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (!token) {
      setError("Missing reset token. Please use the link from your email.");
      return;
    }
    const controller = new AbortController();
    const load = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/auth/setup-password/?token=${encodeURIComponent(token)}`,
          { signal: controller.signal },
        );
        const data = await response.json();
        if (!response.ok || data?.setup_type !== "password_reset") {
          setError(data?.detail || "This reset link is invalid or expired.");
          return;
        }
        setEmail(String(data.email || ""));
        setReady(true);
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Could not check the reset link.");
      }
    };
    void load();
    return () => controller.abort();
  }, [token]);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!ready || saving) return;
    setError("");
    const policyError = validatePassword(password);
    if (policyError) {
      setError(policyError);
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setSaving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/setup-password/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, new_password: password }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data?.detail || "Could not reset your password.");
      setSuccess(true);
      setTimeout(() => navigate("/login", { replace: true }), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset your password.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-md space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Reset Your Password</h1>
          <p className="mt-2 text-sm text-slate-600">This link is valid for 24 hours and can be used once. Your profile information will not change.</p>
        </div>
        {!ready && !error && <p className="text-sm text-slate-600">Checking reset link...</p>}
        {error && <div role="alert" className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
        {success && <div role="status" className="rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">Password updated. Redirecting to login...</div>}
        {ready && !success && (
          <form onSubmit={onSubmit} className="space-y-4">
            <label className="block text-sm text-slate-700">
              Account email
              <input type="email" value={email} readOnly className="mt-1 w-full rounded-lg border bg-slate-100 px-3 py-2" />
            </label>
            <div className="text-sm text-slate-700">
              <label htmlFor="reset-new-password">New Password</label>
              <div className="mt-1 flex rounded-lg border">
                <input id="reset-new-password" type={showPassword ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" required className="min-w-0 flex-1 rounded-l-lg px-3 py-2" />
                <button type="button" onClick={() => setShowPassword(!showPassword)} className="px-3 text-blue-700" aria-label={showPassword ? "Hide new password" : "Show new password"}>{showPassword ? "Hide" : "Show"}</button>
              </div>
            </div>
            <ul className="space-y-1 text-xs text-slate-600" aria-label="Password rules">
              {passwordRules.map((rule) => <li key={rule.label} className={rule.test(password) ? "text-emerald-700" : ""}>{rule.test(password) ? "✓" : "○"} {rule.label}</li>)}
            </ul>
            <div className="text-sm text-slate-700">
              <label htmlFor="reset-confirm-password">Confirm Password</label>
              <div className="mt-1 flex rounded-lg border">
                <input id="reset-confirm-password" type={showConfirm ? "text" : "password"} value={confirm} onChange={(event) => setConfirm(event.target.value)} autoComplete="new-password" required className="min-w-0 flex-1 rounded-l-lg px-3 py-2" />
                <button type="button" onClick={() => setShowConfirm(!showConfirm)} className="px-3 text-blue-700" aria-label={showConfirm ? "Hide confirmation" : "Show confirmation"}>{showConfirm ? "Hide" : "Show"}</button>
              </div>
            </div>
            <button type="submit" disabled={saving} className="portal-btn portal-btn-primary w-full">{saving ? "Saving..." : "Save New Password"}</button>
          </form>
        )}
        <p className="text-xs text-slate-500">Back to <Link to="/login" className="text-blue-600 hover:underline">login</Link></p>
      </div>
    </div>
  );
};

export default ResetPassword;
