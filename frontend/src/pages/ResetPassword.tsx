import React, { useEffect, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { API_BASE_URL } from "../config/api";
import TurnstileWidget from "../components/TurnstileWidget";
import { passwordRules, validatePassword } from "../utils/passwordPolicy";

type ResetLocationState = { email?: string } | null;

const ResetPassword: React.FC = () => {
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const legacyToken = searchParams.get("token") || "";
  const state = location.state as ResetLocationState;
  const [email, setEmail] = useState(state?.email || "");
  const [otp, setOtp] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [legacyReady, setLegacyReady] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [saving, setSaving] = useState(false);
  const [resending, setResending] = useState(false);
  const [success, setSuccess] = useState(false);
  const [captchaToken, setCaptchaToken] = useState("");
  const [captchaVersion, setCaptchaVersion] = useState(0);
  const hasCaptcha = Boolean(import.meta.env.VITE_TURNSTILE_SITE_KEY);

  useEffect(() => {
    if (!legacyToken) return;
    const controller = new AbortController();
    const load = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/auth/setup-password/?token=${encodeURIComponent(legacyToken)}`,
          { signal: controller.signal },
        );
        const data = await response.json();
        if (!response.ok || data?.setup_type !== "password_reset") {
          setError(data?.detail || "This reset link is invalid or expired.");
          return;
        }
        setEmail(String(data.email || ""));
        setLegacyReady(true);
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Could not check the reset link.");
      }
    };
    void load();
    return () => controller.abort();
  }, [legacyToken]);

  const readResponse = async (response: Response) => {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data?.detail || "The request could not be completed.");
    return data;
  };

  const verifyCode = async (event: React.FormEvent) => {
    event.preventDefault();
    if (verifying) return;
    setError("");
    setNotice("");
    if (!email.trim() || !/^\d{6}$/.test(otp)) {
      setError("Enter your email and the six-digit code from your message.");
      return;
    }
    setVerifying(true);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/password-reset/verify/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase(), otp }),
      });
      const data = await readResponse(response);
      setResetToken(String(data.reset_token || ""));
      setNotice("Code verified. Create your new password.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "The code is invalid or expired.");
    } finally {
      setVerifying(false);
    }
  };

  const resendCode = async () => {
    if (!email.trim() || resending) return;
    if (hasCaptcha && !captchaToken) {
      setError("Please complete the captcha before requesting another code.");
      return;
    }
    setError("");
    setNotice("");
    setResending(true);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/password-reset/request/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          captcha_token: captchaToken || undefined,
        }),
      });
      const data = await readResponse(response);
      setOtp("");
      setCaptchaToken("");
      setCaptchaVersion((current) => current + 1);
      setNotice(data?.detail || "If the account exists, a new code has been sent.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not resend the code.");
    } finally {
      setResending(false);
    }
  };

  const savePassword = async (event: React.FormEvent) => {
    event.preventDefault();
    if (saving) return;
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
      const endpoint = legacyToken ? "auth/setup-password/" : "auth/password-reset/complete/";
      const body = legacyToken
        ? { token: legacyToken, new_password: password }
        : { reset_token: resetToken, new_password: password, confirm_password: confirm };
      const response = await fetch(`${API_BASE_URL}/${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      await readResponse(response);
      setSuccess(true);
      setTimeout(() => navigate("/login", { replace: true }), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset your password.");
    } finally {
      setSaving(false);
    }
  };

  const passwordStepReady = legacyToken ? legacyReady : Boolean(resetToken);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4">
      <div className="w-full max-w-md space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Reset Your Password</h1>
          <p className="mt-2 text-sm text-slate-600">
            {legacyToken
              ? "This legacy reset link can be used once before it expires."
              : resetToken
                ? "Choose a new password for your account."
                : "Enter the six-digit code sent to your email. Codes expire after 10 minutes."}
          </p>
        </div>
        {error && <div role="alert" className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</div>}
        {notice && <div role="status" className="rounded border border-blue-200 bg-blue-50 p-3 text-sm text-blue-700">{notice}</div>}
        {success && <div role="status" className="rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">Password updated. Redirecting to login...</div>}

        {!legacyToken && !resetToken && !success && (
          <form onSubmit={verifyCode} className="space-y-4">
            <label className="block text-sm text-slate-700">
              Account email
              <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required className="mt-1 w-full rounded-lg border px-3 py-2" />
            </label>
            <label className="block text-sm text-slate-700">
              Six-digit code
              <input inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={otp} onChange={(event) => setOtp(event.target.value.replace(/\D/g, "").slice(0, 6))} autoComplete="one-time-code" required className="mt-1 w-full rounded-lg border px-3 py-2 text-center text-xl tracking-[0.35em]" />
            </label>
            {hasCaptcha && <TurnstileWidget key={captchaVersion} onToken={setCaptchaToken} />}
            <button type="submit" disabled={verifying} className="portal-btn portal-btn-primary w-full">{verifying ? "Verifying..." : "Verify Code"}</button>
            <button type="button" disabled={resending || !email.trim() || (hasCaptcha && !captchaToken)} onClick={() => void resendCode()} className="portal-btn portal-btn-ghost w-full">{resending ? "Sending..." : "Send Another Code"}</button>
          </form>
        )}

        {legacyToken && !legacyReady && !error && <p className="text-sm text-slate-600">Checking reset link...</p>}
        {passwordStepReady && !success && (
          <form onSubmit={savePassword} className="space-y-4">
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
