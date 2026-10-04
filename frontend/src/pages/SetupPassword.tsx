import React, { useMemo, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { API_BASE_URL } from "../config/api";

const ACCOUNT_AGENCIES = [
  { code: "DPWH", name: "Department of Public Works and Highways" },
  { code: "DENR", name: "Department of Environment and Natural Resources" },
  { code: "RDC-NCR", name: "Regional Development Council National Capital Region" },
  { code: "DILG", name: "Department of the Interior and Local Government" },
  { code: "DEPDev", name: "Department of Economy, Planning, and Development" },
  { code: "DBM", name: "Department of Budget and Management" },
  { code: "DA", name: "Department of Agriculture" },
  { code: "DAR", name: "Department of Agrarian Reform" },
  { code: "DepEd", name: "Department of Education" },
  { code: "DOH", name: "Department of Health" },
  { code: "DHSUD", name: "Department of Human Settlements and Urban Development" },
  { code: "DICT", name: "Department of Information and Communications Technology" },
  { code: "DOLE", name: "Department of Labor and Employment" },
  { code: "DOST", name: "Department of Science and Technology" },
  { code: "DSWD", name: "Department of Social Welfare and Development" },
  { code: "DOT", name: "Department of Tourism" },
  { code: "DTI", name: "Department of Trade and Industry" },
  { code: "DOTr", name: "Department of Transportation" },
  { code: "TESDA", name: "Technical Education and Skills Development Authority" },
  { code: "CHED", name: "Commission on Higher Education" },
  { code: "PSA", name: "Philippine Statistics Authority" },
] as const;

const normalizeAgency = (value: string) => {
  const normalized = value.trim().replace(/\s+/g, " ").toLowerCase();
  return ACCOUNT_AGENCIES.find(
    (agency) =>
      agency.code.toLowerCase() === normalized ||
      agency.name.toLowerCase() === normalized,
  )?.code;
};

const hasAgencySearchMatch = (value: string) => {
  const normalized = value.trim().replace(/\s+/g, " ").toLowerCase();
  if (!normalized) return true;
  return ACCOUNT_AGENCIES.some(
    (agency) =>
      agency.code.toLowerCase().includes(normalized) ||
      agency.name.toLowerCase().includes(normalized),
  );
};

const searchAgencies = (value: string) => {
  const normalized = value.trim().replace(/\s+/g, " ").toLowerCase();
  if (!normalized) return ACCOUNT_AGENCIES;
  return ACCOUNT_AGENCIES.filter(
    (agency) =>
      agency.code.toLowerCase().includes(normalized) ||
      agency.name.toLowerCase().includes(normalized),
  );
};

const keyboardSymbols = "!\"#$%&'()*+,-./:;<=>?@[\\]^_\x60{|}~";
const hasKeyboardSymbol = (value: string) =>
  Array.from(value).some((character) => keyboardSymbols.includes(character));

const passwordRules = [
  { label: "At least 12 characters", test: (v: string) => v.length >= 12 },
  { label: "At least 1 uppercase letter", test: (v: string) => /[A-Z]/.test(v) },
  { label: "At least 1 lowercase letter", test: (v: string) => /[a-z]/.test(v) },
  { label: "At least 1 number", test: (v: string) => /[0-9]/.test(v) },
  { label: "At least 1 symbol or special character", test: hasKeyboardSymbol },
];

const validatePassword = (value: string) => {
  if (value.length < 12) return "Password must be at least 12 characters.";
  if (!/[A-Z]/.test(value)) return "Password must include an uppercase letter.";
  if (!/[a-z]/.test(value)) return "Password must include a lowercase letter.";
  if (!/[0-9]/.test(value)) return "Password must include a number.";
  if (!hasKeyboardSymbol(value)) return "Password must include a symbol.";
  return "";
};

const SetupPassword: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";

  const [email, setEmail] = useState("");
  const [agencyLocked, setAgencyLocked] = useState(false);
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
  const [agencyOpen, setAgencyOpen] = useState(false);
  const [agencySearchDirty, setAgencySearchDirty] = useState(false);
  const [agencyTouched, setAgencyTouched] = useState(false);
  const [agencyActiveIndex, setAgencyActiveIndex] = useState(0);
  const [agencyListAbove, setAgencyListAbove] = useState(false);
  const [agencyListHeight, setAgencyListHeight] = useState(224);
  const agencyPickerRef = React.useRef<HTMLDivElement>(null);
  const agencyInputRef = React.useRef<HTMLInputElement>(null);
  const agencyListRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!token) return;
    const loadProfile = async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/auth/setup-password/?token=${encodeURIComponent(token)}`);
        const data = await res.json();
        if (!res.ok) return;
        setEmail(String(data?.email || ""));
        setAgencyLocked(data?.agency_locked === true);
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
  const agencyOptions = useMemo(
    () => searchAgencies(agencySearchDirty ? profile.agency : ""),
    [agencySearchDirty, profile.agency],
  );
  const agencyUnavailable =
    !hasAgencySearchMatch(profile.agency) ||
    (agencyTouched && !normalizeAgency(profile.agency));

  React.useEffect(() => {
    if (!agencyOpen) return;
    const updatePlacement = () => {
      const input = agencyInputRef.current;
      if (!input) return;
      const rect = input.getBoundingClientRect();
      const viewport = window.visualViewport;
      const top = viewport?.offsetTop ?? 0;
      const bottom = top + (viewport?.height ?? window.innerHeight);
      const below = bottom - rect.bottom;
      const above = rect.top - top;
      const placeAbove = below < 180 && above > below;
      setAgencyListAbove(placeAbove);
      setAgencyListHeight(Math.max(80, Math.min(224, (placeAbove ? above : below) - 12)));
    };
    const handleViewportResize = () => {
      const input = agencyInputRef.current;
      const viewport = window.visualViewport;
      if (input) {
        const rect = input.getBoundingClientRect();
        const top = viewport?.offsetTop ?? 0;
        const bottom = top + (viewport?.height ?? window.innerHeight);
        if (rect.top < top || rect.bottom > bottom) {
          input.scrollIntoView({ block: "center" });
        }
      }
      window.requestAnimationFrame(updatePlacement);
    };
    const closeOnOutsideTap = (event: PointerEvent) => {
      if (!agencyPickerRef.current?.contains(event.target as Node)) {
        setAgencyOpen(false);
        setAgencyTouched(true);
      }
    };
    updatePlacement();
    window.requestAnimationFrame(updatePlacement);
    document.addEventListener("pointerdown", closeOnOutsideTap);
    window.addEventListener("resize", handleViewportResize);
    window.visualViewport?.addEventListener("resize", handleViewportResize);
    window.visualViewport?.addEventListener("scroll", updatePlacement);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideTap);
      window.removeEventListener("resize", handleViewportResize);
      window.visualViewport?.removeEventListener("resize", handleViewportResize);
      window.visualViewport?.removeEventListener("scroll", updatePlacement);
    };
  }, [agencyOpen]);

  React.useEffect(() => {
    if (!agencyOpen || !agencyListRef.current) return;
    const active = agencyListRef.current.children[agencyActiveIndex] as HTMLElement | undefined;
    if (active) {
      const list = agencyListRef.current;
      if (active.offsetTop < list.scrollTop) list.scrollTop = active.offsetTop;
      if (active.offsetTop + active.offsetHeight > list.scrollTop + list.clientHeight) {
        list.scrollTop = active.offsetTop + active.offsetHeight - list.clientHeight;
      }
    }
  }, [agencyActiveIndex, agencyOpen, agencyOptions]);

  const selectAgency = (code: string) => {
    setProfile((previous) => ({ ...previous, agency: code }));
    setAgencyOpen(false);
    setAgencySearchDirty(false);
    setAgencyTouched(true);
    setAgencyActiveIndex(0);
  };

  const openAgencyList = () => {
    setAgencySearchDirty(!normalizeAgency(profile.agency) && Boolean(profile.agency.trim()));
    setAgencyActiveIndex(0);
    setAgencyOpen(true);
  };

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
      (item) =>
        (item.key !== "agency" || !agencyLocked) &&
        !String((profile as Record<string, string>)[item.key] || "").trim(),
    );
    if (missing.length > 0) {
      setError(`Please complete: ${missing.map((m) => m.label).join(", ")}.`);
      return;
    }
    const agency = agencyLocked ? profile.agency : normalizeAgency(profile.agency);
    if (!agencyLocked && !agency) {
      setAgencyTouched(true);
      setError("This is an invalid Agency");
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
        body: JSON.stringify({ token, new_password: password, ...profile, agency }),
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
              {agencyLocked ? (
                <div className="block min-w-0">
                  <label htmlFor="registration-agency" className="text-sm text-slate-700">Agency{profile.agency ? " *" : ""}</label>
                  <input
                    id="registration-agency"
                    name="agency"
                    type="text"
                    value={profile.agency}
                    placeholder="No agency on record"
                    readOnly
                    aria-describedby="registration-agency-help"
                    className="mt-1 w-full min-w-0 rounded-lg border border-slate-300 bg-slate-100 px-3 py-2 text-slate-700"
                  />
                  <p id="registration-agency-help" className="mt-1 text-xs text-slate-500">
                    {profile.agency
                      ? "This agency is saved on your account and cannot be changed here."
                      : "No agency is saved on your account. Contact an administrator to update it."}
                  </p>
                </div>
              ) : (
              <div className="block min-w-0" ref={agencyPickerRef}>
                <label htmlFor="registration-agency" className="text-sm text-slate-700">Agency *</label>
                <div className="relative mt-1">
                  <input
                    ref={agencyInputRef}
                    type="text"
                    id="registration-agency"
                    name="agency"
                    role="combobox"
                    aria-autocomplete="list"
                    aria-expanded={agencyOpen}
                    aria-controls="registration-agency-options"
                    aria-activedescendant={agencyOpen && agencyOptions.length > 0 ? `registration-agency-option-${agencyOptions[agencyActiveIndex]?.code}` : undefined}
                    placeholder="Search or select agency"
                    value={profile.agency}
                    onFocus={openAgencyList}
                    onClick={() => { if (!agencyOpen) openAgencyList(); }}
                    onChange={(e) => {
                      setProfile((p) => ({ ...p, agency: e.target.value }));
                      setAgencySearchDirty(true);
                      setAgencyTouched(false);
                      setAgencyActiveIndex(0);
                      setAgencyOpen(true);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                        e.preventDefault();
                        if (!agencyOpen) {
                          setAgencyActiveIndex(e.key === "ArrowUp" ? Math.max(0, agencyOptions.length - 1) : 0);
                          setAgencyOpen(true);
                        } else if (agencyOptions.length > 0) {
                          setAgencyActiveIndex((index) => (index + (e.key === "ArrowDown" ? 1 : -1) + agencyOptions.length) % agencyOptions.length);
                        }
                      } else if (e.key === "Enter" && agencyOpen && agencyOptions.length > 0) {
                        e.preventDefault();
                        selectAgency(agencyOptions[agencyActiveIndex].code);
                      } else if (e.key === "Escape") {
                        setAgencyOpen(false);
                        setAgencyTouched(true);
                      } else if (e.key === "Tab") {
                        setAgencyOpen(false);
                        setAgencyTouched(true);
                      }
                    }}
                    onInvalid={() => setAgencyTouched(true)}
                    className={`w-full min-w-0 rounded-lg border px-3 py-2 pr-9 ${
                      agencyUnavailable
                        ? "border-rose-500 focus:border-rose-500 focus:ring-rose-500"
                        : ""
                    }`}
                    autoComplete="off"
                    aria-invalid={agencyUnavailable}
                    aria-describedby="registration-agency-help"
                    required
                  />
                  <span aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-500">▾</span>
                  {agencyOpen && (
                    <div
                      ref={agencyListRef}
                      id="registration-agency-options"
                      role="listbox"
                      aria-label="Approved agencies"
                      className={`absolute inset-x-0 z-30 overflow-y-auto overscroll-contain rounded-lg border border-slate-300 bg-white shadow-lg ${agencyListAbove ? "bottom-full mb-1" : "top-full mt-1"}`}
                      style={{ maxHeight: agencyListHeight }}
                    >
                      {agencyOptions.length > 0 ? agencyOptions.map((agency, index) => (
                        <div
                          key={agency.code}
                          id={`registration-agency-option-${agency.code}`}
                          role="option"
                          aria-selected={index === agencyActiveIndex}
                          onMouseEnter={() => setAgencyActiveIndex(index)}
                          onClick={() => selectAgency(agency.code)}
                          className={`min-h-11 cursor-pointer px-3 py-2 text-sm ${index === agencyActiveIndex ? "bg-blue-50" : "hover:bg-slate-50"}`}
                        >
                          <span className="block font-medium text-slate-900">{agency.code}</span>
                          <span className="block break-words text-slate-600">{agency.name}</span>
                        </div>
                      )) : (
                        <div className="px-3 py-3 text-sm text-slate-600">No approved agencies found.</div>
                      )}
                    </div>
                  )}
                </div>
                <p
                  id="registration-agency-help"
                  className={`mt-1 text-xs ${agencyUnavailable ? "text-rose-600" : "text-slate-500"}`}
                  role={agencyUnavailable ? "alert" : undefined}
                >
                  {agencyUnavailable
                    ? "This is an invalid Agency"
                    : "Search using the agency acronym or full name."}
                </p>
              </div>
              )}
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
                  This email will be used to sign in. Your full name will be shown as your username.
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
