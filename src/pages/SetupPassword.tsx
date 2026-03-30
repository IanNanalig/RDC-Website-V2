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

  const [email, setEmail] = useState("");
  const [profile, setProfile] = useState({
    full_name: "",
    agency: "",
    agency_head: "",
    office: "",
    division: "",
    position: "",
    contact_number: "",
    phone_number: "",
  });
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [loading, setLoading] = useState(false);

  React.useEffect(() => {
    if (!token) return;
    const loadProfile = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/auth/setup-password/?token=${encodeURIComponent(token)}`);
        const data = await res.json();
        if (!res.ok) return;
        setEmail(String(data?.email || ""));
        if (data?.profile) {
          setProfile((prev) => ({ ...prev, ...data.profile }));
        }
      } catch {
        // ignore prefill errors
      }
    };
    loadProfile();
  }, [token]);

  const policyError = useMemo(() => validatePassword(password), [password]);
  const confirmError = useMemo(
    () => (confirm && password !== confirm ? "Passwords do not match." : ""),
    [password, confirm],
  );

  const profileRequired = [
    { key: "full_name", label: "Full Name" },
    { key: "agency", label: "Agency" },
    { key: "agency_head", label: "Current Head of Agency/Local Chief Executive" },
    { key: "office", label: "Office" },
    { key: "division", label: "Division" },
    { key: "position", label: "Position" },
    { key: "contact_number", label: "Contact Number" },
    { key: "phone_number", label: "Phone Number" },
  ] as const;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!token) {
      setError("Missing setup token. Please use the link from your email.");
      return;
    }
    const missing = profileRequired.filter(
      (item) => !String((profile as Record<string, string>)[item.key] || "").trim(),
    );
    if (missing.length > 0) {
      setError(`Please complete: ${missing.map((m) => m.label).join(", ")}.`);
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
        body: JSON.stringify({ token, new_password: password, ...profile }),
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
      <div className="w-full max-w-3xl bg-white rounded-xl shadow-lg border border-slate-200 p-6 sm:p-8 space-y-6">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">RDC Portal Registration</p>
          <h1 className="text-2xl sm:text-3xl font-semibold text-slate-900">Complete Your Profile</h1>
          <p className="text-sm text-slate-600 mt-2">
            Please complete the registration form, then set your password to access the RDC Portal.
          </p>
        </div>
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

        <form onSubmit={onSubmit} className="space-y-6">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Profile Information</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <label className="block">
                <span className="text-sm text-slate-700">Full Name *</span>
                <input
                  type="text"
                  value={profile.full_name}
                  onChange={(e) => setProfile((p) => ({ ...p, full_name: e.target.value }))}
                  className="mt-1 w-full border rounded-lg px-3 py-2"
                  required
                />
              </label>
              <label className="block">
                <span className="text-sm text-slate-700">Agency *</span>
                <input
                  type="text"
                  value={profile.agency}
                  onChange={(e) => setProfile((p) => ({ ...p, agency: e.target.value }))}
                  className="mt-1 w-full border rounded-lg px-3 py-2"
                  required
                />
              </label>
              <label className="block md:col-span-2">
                <span className="text-sm text-slate-700">Current Head of Agency/Local Chief Executive *</span>
                <input
                  type="text"
                  value={profile.agency_head}
                  onChange={(e) => setProfile((p) => ({ ...p, agency_head: e.target.value }))}
                  className="mt-1 w-full border rounded-lg px-3 py-2"
                  required
                />
              </label>
              <label className="block">
                <span className="text-sm text-slate-700">Office *</span>
                <input
                  type="text"
                  value={profile.office}
                  onChange={(e) => setProfile((p) => ({ ...p, office: e.target.value }))}
                  className="mt-1 w-full border rounded-lg px-3 py-2"
                  required
                />
              </label>
              <label className="block">
                <span className="text-sm text-slate-700">Division *</span>
                <input
                  type="text"
                  value={profile.division}
                  onChange={(e) => setProfile((p) => ({ ...p, division: e.target.value }))}
                  className="mt-1 w-full border rounded-lg px-3 py-2"
                  required
                />
              </label>
              <label className="block">
                <span className="text-sm text-slate-700">Position *</span>
                <input
                  type="text"
                  value={profile.position}
                  onChange={(e) => setProfile((p) => ({ ...p, position: e.target.value }))}
                  className="mt-1 w-full border rounded-lg px-3 py-2"
                  required
                />
              </label>
              <label className="block">
                <span className="text-sm text-slate-700">Contact Number *</span>
                <input
                  type="text"
                  value={profile.contact_number}
                  onChange={(e) => setProfile((p) => ({ ...p, contact_number: e.target.value }))}
                  className="mt-1 w-full border rounded-lg px-3 py-2"
                  required
                />
              </label>
              <label className="block">
                <span className="text-sm text-slate-700">Phone Number *</span>
                <input
                  type="text"
                  value={profile.phone_number}
                  onChange={(e) => setProfile((p) => ({ ...p, phone_number: e.target.value }))}
                  className="mt-1 w-full border rounded-lg px-3 py-2"
                  required
                />
              </label>
              <label className="block md:col-span-2">
                <span className="text-sm text-slate-700">Email Address *</span>
                <input
                  type="email"
                  value={email}
                  readOnly
                  className="mt-1 w-full border rounded-lg px-3 py-2 bg-slate-100 text-slate-600"
                />
                <p className="text-xs text-slate-500 mt-1">
                  This email will be used as your username.
                </p>
              </label>
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 p-4">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Set Your Password</h2>
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
          </div>
        </form>

        <div className="text-xs text-slate-500">
          Need help? <Link to="/login" className="text-blue-600 hover:underline">Back to login</Link>
        </div>
      </div>
    </div>
  );
};

export default SetupPassword;
