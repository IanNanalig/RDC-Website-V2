import React, { useMemo, useState } from "react";
import { useNavigate, useSearchParams, Link } from "react-router-dom";
import { API_BASE_URL } from "../config/api";
import { passwordRules, validatePassword } from "../utils/passwordPolicy";
import { contactNumberError, formatContactNumber, sanitizeContactNumber } from "../utils/contactNumbers";
import { personNameError } from "../utils/personName";

type AgencyOption = { code: string; name: string; head_name?: string };

const normalizeAgency = (value: string, agencies: AgencyOption[]) => {
  const normalized = value.trim().replace(/\s+/g, " ").toLowerCase();
  return agencies.find(
    (agency) =>
      agency.code.toLowerCase() === normalized ||
      agency.name.toLowerCase() === normalized,
  )?.code;
};

const hasAgencySearchMatch = (value: string, agencies: AgencyOption[]) => {
  const normalized = value.trim().replace(/\s+/g, " ").toLowerCase();
  if (!normalized) return true;
  return agencies.some(
    (agency) =>
      agency.code.toLowerCase().includes(normalized) ||
      agency.name.toLowerCase().includes(normalized),
  );
};

const searchAgencies = (value: string, agencies: AgencyOption[]) => {
  const normalized = value.trim().replace(/\s+/g, " ").toLowerCase();
  if (!normalized) return agencies;
  return agencies.filter(
    (agency) =>
      agency.code.toLowerCase().includes(normalized) ||
      agency.name.toLowerCase().includes(normalized),
  );
};

const SetupPassword: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";

  const [email, setEmail] = useState("");
  const [agencyLocked, setAgencyLocked] = useState(false);
  const [agencies, setAgencies] = useState<AgencyOption[]>([]);
  const [setupType, setSetupType] = useState("existing_account");
  const [profile, setProfile] = useState({
    first_name: "",
    last_name: "",
    agency: "",
    agency_head: "",
    division: "",
    position: "",
    contact_number: "02",
    phone_number: "09",
  });
  const [contactNumbersTouched, setContactNumbersTouched] = useState({ contact_number: false, phone_number: false });
  const [nameFieldsTouched, setNameFieldsTouched] = useState({ first_name: false, last_name: false });
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [error, setError] = useState("");
  const [linkInvalid, setLinkInvalid] = useState(false);
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
        if (!res.ok) {
          setLinkInvalid(true);
          setError(data?.detail || "This registration link is invalid or expired.");
          return;
        }
        if (data?.setup_type === "password_reset") {
          navigate(`/reset-password?token=${encodeURIComponent(token)}`, { replace: true });
          return;
        }
        setLinkInvalid(false);
        setEmail(String(data?.email || ""));
        setSetupType(String(data?.setup_type || "existing_account"));
        setAgencyLocked(data?.agency_locked === true);
        if (Array.isArray(data?.agencies) && data.agencies.length) {
          setAgencies(data.agencies.map((agency: AgencyOption) => ({
            code: String(agency.code || ""),
            name: String(agency.name || ""),
            head_name: String(agency.head_name || ""),
          })).filter((agency: AgencyOption) => agency.code && agency.name));
        }
        if (data?.profile) {
          setProfile((prev) => ({
            ...prev,
            ...data.profile,
            contact_number: sanitizeContactNumber(String(data.profile.contact_number || "02"), "contact_number"),
            phone_number: sanitizeContactNumber(String(data.profile.phone_number || "09"), "phone_number"),
          }));
        }
      } catch {
        // ignore prefill errors
      }
    };
    loadProfile();
  }, [token, navigate]);

  const policyError = useMemo(() => validatePassword(password), [password]);
  const confirmError = useMemo(
    () => (confirm && password !== confirm ? "Passwords do not match." : ""),
    [password, confirm],
  );
  const agencyOptions = useMemo(
    () => searchAgencies(agencySearchDirty ? profile.agency : "", agencies),
    [agencySearchDirty, profile.agency, agencies],
  );
  const agencyUnavailable =
    !hasAgencySearchMatch(profile.agency, agencies) ||
    (agencyTouched && !normalizeAgency(profile.agency, agencies));

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
    const selected = agencies.find((agency) => agency.code === code);
    setProfile((previous) => ({
      ...previous,
      agency: code,
      agency_head: selected?.head_name || "",
    }));
    setAgencyOpen(false);
    setAgencySearchDirty(false);
    setAgencyTouched(true);
    setAgencyActiveIndex(0);
  };

  const openAgencyList = () => {
    setAgencySearchDirty(!normalizeAgency(profile.agency, agencies) && Boolean(profile.agency.trim()));
    setAgencyActiveIndex(0);
    setAgencyOpen(true);
  };

  const profileRequired = [
    { key: "first_name", label: "First Name" },
    { key: "last_name", label: "Last Name" },
    { key: "agency", label: "Agency / Office" },
    { key: "division", label: "Division" },
    { key: "position", label: "Position" },
    { key: "contact_number", label: "Office Contact No." },
    { key: "phone_number", label: "Phone Number" },
  ] as const;

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setContactNumbersTouched({ contact_number: true, phone_number: true });
    setNameFieldsTouched({ first_name: true, last_name: true });
    setError("");
    setSuccess("");
    if (!token) {
      setError("Missing setup token. Please use the link from your email.");
      return;
    }
    if (linkInvalid) {
      setError("This registration link is invalid or expired. Ask an administrator to resend it.");
      return;
    }
    if (personNameError(profile.first_name, "first_name") || personNameError(profile.last_name, "last_name")) return;
    if (contactNumberError(profile.contact_number, "contact_number") || contactNumberError(profile.phone_number, "phone_number")) {
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
    const agency = agencyLocked ? profile.agency : normalizeAgency(profile.agency, agencies);
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
    if (setupType === "invitation" && !window.confirm(
      `Complete registration for ${email || "your email address"}?\n\n` +
      "Your account will remain inactive until an administrator activates it. Continue?",
    )) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/setup-password/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          token,
          new_password: password,
          first_name: profile.first_name.trim(),
          last_name: profile.last_name.trim(),
          agency,
          office: agency,
          division: profile.division.trim(),
          position: profile.position.trim(),
          contact_number: profile.contact_number,
          phone_number: profile.phone_number,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Failed to set password.");
      }
      if (data?.requires_admin_activation || setupType === "invitation") {
        setSuccess("Registration complete. Your account is inactive until an administrator activates it.");
        setTimeout(() => navigate("/login", { replace: true, state: { registrationPendingActivation: true } }), 1500);
      } else {
        setSuccess("Password set successfully. You can now log in.");
        setTimeout(() => navigate("/login", { replace: true }), 1500);
      }
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

        <form onSubmit={onSubmit} noValidate className="space-y-6">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <h2 className="text-sm font-semibold text-slate-700 mb-3">Profile Information</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="block">
                <label htmlFor="registration-first-name" className="text-sm text-slate-700">First Name</label>
                <input
                  id="registration-first-name"
                  name="first_name"
                  type="text"
                  value={profile.first_name}
                  onChange={(e) => setProfile((p) => ({ ...p, first_name: e.target.value }))}
                  onBlur={() => setNameFieldsTouched((value) => ({ ...value, first_name: true }))}
                  maxLength={150}
                  placeholder="Enter first name"
                  aria-invalid={nameFieldsTouched.first_name && Boolean(personNameError(profile.first_name, "first_name"))}
                  aria-describedby={nameFieldsTouched.first_name && personNameError(profile.first_name, "first_name") ? "registration-first-name-example registration-first-name-error" : "registration-first-name-example"}
                  className="mt-1 w-full border rounded-lg px-3 py-2"
                  required
                />
                <span id="registration-first-name-example" className="mt-1 block text-xs text-slate-500">Ex. Juan</span>
                {nameFieldsTouched.first_name && personNameError(profile.first_name, "first_name") && <span id="registration-first-name-error" role="alert" className="mt-1 block text-xs text-rose-600">{personNameError(profile.first_name, "first_name")}</span>}
              </div>
              <div className="block">
                <label htmlFor="registration-last-name" className="text-sm text-slate-700">Last Name</label>
                <input
                  id="registration-last-name"
                  name="last_name"
                  type="text"
                  value={profile.last_name}
                  onChange={(e) => setProfile((p) => ({ ...p, last_name: e.target.value }))}
                  onBlur={() => setNameFieldsTouched((value) => ({ ...value, last_name: true }))}
                  maxLength={150}
                  placeholder="Enter last name"
                  aria-invalid={nameFieldsTouched.last_name && Boolean(personNameError(profile.last_name, "last_name"))}
                  aria-describedby={nameFieldsTouched.last_name && personNameError(profile.last_name, "last_name") ? "registration-last-name-example registration-last-name-error" : "registration-last-name-example"}
                  className="mt-1 w-full border rounded-lg px-3 py-2"
                  required
                />
                <span id="registration-last-name-example" className="mt-1 block text-xs text-slate-500">Ex. Dela Cruz</span>
                {nameFieldsTouched.last_name && personNameError(profile.last_name, "last_name") && <span id="registration-last-name-error" role="alert" className="mt-1 block text-xs text-rose-600">{personNameError(profile.last_name, "last_name")}</span>}
              </div>
              {agencyLocked ? (
                <div className="block min-w-0">
                  <label htmlFor="registration-agency" className="text-sm text-slate-700">Agency / Office</label>
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
                      ? "This agency and office are saved on your account and cannot be changed here."
                      : "No agency or office is saved on your account. Contact an administrator to update it."}
                  </p>
                </div>
              ) : (
              <div className="block min-w-0" ref={agencyPickerRef}>
                <label htmlFor="registration-agency" className="text-sm text-slate-700">Agency / Office</label>
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
                      const value = e.target.value;
                      const selected = agencies.find((agency) =>
                        agency.code.toLowerCase() === value.trim().toLowerCase() ||
                        agency.name.toLowerCase() === value.trim().toLowerCase(),
                      );
                      setProfile((p) => ({ ...p, agency: value, agency_head: selected?.head_name || "" }));
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
              <div className="block md:col-span-2">
                <label htmlFor="registration-agency-head" className="text-sm text-slate-700">Current Head of Agency/Local Chief Executive</label>
                <input
                  id="registration-agency-head"
                  type="text"
                  value={profile.agency_head}
                  readOnly
                  aria-readonly="true"
                  placeholder="Not yet configured by the Administrator"
                  className="mt-1 w-full border rounded-lg bg-slate-100 px-3 py-2 text-slate-700"
                />
                <span className="mt-1 block text-xs text-slate-500">Ex. Mayor Vico Sotto</span>
                <span className="mt-0.5 block text-xs text-slate-500">Automatically supplied from the selected agency. Contact an Administrator if it needs updating.</span>
              </div>
              <div className="block">
                <label htmlFor="registration-division" className="text-sm text-slate-700">Division</label>
                <input
                  id="registration-division"
                  type="text"
                  value={profile.division}
                  onChange={(e) => setProfile((p) => ({ ...p, division: e.target.value }))}
                  aria-required="true"
                  className="mt-1 w-full border rounded-lg px-3 py-2"
                  required
                />
                <span className="mt-1 block text-xs text-slate-500">Ex. Planning Office</span>
              </div>
              <div className="block">
                <label htmlFor="registration-position" className="text-sm text-slate-700">Position</label>
                <input
                  id="registration-position"
                  type="text"
                  value={profile.position}
                  onChange={(e) => setProfile((p) => ({ ...p, position: e.target.value }))}
                  aria-required="true"
                  className="mt-1 w-full border rounded-lg px-3 py-2"
                  required
                />
                <span className="mt-1 block text-xs text-slate-500">Ex. Validator</span>
              </div>
              <label className="block">
                <span className="text-sm text-slate-700">Office Contact No.</span>
                <input
                  type="text"
                  inputMode="numeric"
                  placeholder="02 xxxx xxxx"
                  value={formatContactNumber(profile.contact_number, "contact_number")}
                  onChange={(e) => setProfile((p) => ({ ...p, contact_number: sanitizeContactNumber(e.target.value, "contact_number") }))}
                  onBlur={() => setContactNumbersTouched((value) => ({ ...value, contact_number: true }))}
                  aria-required="true"
                  aria-invalid={contactNumbersTouched.contact_number && Boolean(contactNumberError(profile.contact_number, "contact_number"))}
                  className={`mt-1 w-full border rounded-lg px-3 py-2 ${contactNumbersTouched.contact_number && contactNumberError(profile.contact_number, "contact_number") ? "border-rose-500" : ""}`}
                  required
                />
                <span className="mt-1 block text-xs text-slate-500">Required: 02 xxxx xxxx</span>
                {contactNumbersTouched.contact_number && contactNumberError(profile.contact_number, "contact_number") && <span role="alert" className="mt-1 block text-xs text-rose-600">{contactNumberError(profile.contact_number, "contact_number")}</span>}
              </label>
              <label className="block">
                <span className="text-sm text-slate-700">Phone Number</span>
                <input
                  type="text"
                  inputMode="numeric"
                  placeholder="09xx xxx xxxx"
                  value={formatContactNumber(profile.phone_number, "phone_number")}
                  onChange={(e) => setProfile((p) => ({ ...p, phone_number: sanitizeContactNumber(e.target.value, "phone_number") }))}
                  onBlur={() => setContactNumbersTouched((value) => ({ ...value, phone_number: true }))}
                  aria-required="true"
                  aria-invalid={contactNumbersTouched.phone_number && Boolean(contactNumberError(profile.phone_number, "phone_number"))}
                  className={`mt-1 w-full border rounded-lg px-3 py-2 ${contactNumbersTouched.phone_number && contactNumberError(profile.phone_number, "phone_number") ? "border-rose-500" : ""}`}
                  required
                />
                <span className="mt-1 block text-xs text-slate-500">Required: 09xx xxx xxxx</span>
                {contactNumbersTouched.phone_number && contactNumberError(profile.phone_number, "phone_number") && <span role="alert" className="mt-1 block text-xs text-rose-600">{contactNumberError(profile.phone_number, "phone_number")}</span>}
              </label>
              <label className="block md:col-span-2">
                <span className="text-sm text-slate-700">Email Address</span>
                <input
                  type="email"
                  value={email}
                  readOnly
                  className="mt-1 w-full border rounded-lg px-3 py-2 bg-slate-100 text-slate-600"
                />
                <p className="text-xs text-slate-500 mt-1">
                  This email will be used to sign in. Your name will be shown as your username.
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
                className={`w-full rounded-lg border px-3 py-2 pr-10 ${password && policyError ? "border-rose-500 focus:ring-rose-200" : ""}`}
                autoComplete="new-password"
                aria-invalid={Boolean(password && policyError)}
                aria-describedby="setup-password-rules setup-password-validity"
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
          {confirm && confirmError && <p role="alert" className="mt-1 text-xs font-medium text-rose-700">{confirmError}</p>}

          <div id="setup-password-rules" className="text-xs text-slate-600 space-y-1">
            <div className="font-semibold text-slate-700">Password rules:</div>
            <ul className="space-y-1">
              {passwordRules.map((rule) => {
                const ok = rule.test(password);
                return (
                  <li key={rule.label} className={`flex items-center gap-2 ${ok ? "text-emerald-600" : password ? "text-rose-600" : "text-slate-500"}`}>
                    <span
                      className={`inline-flex h-4 w-4 items-center justify-center rounded-full border ${
                        ok ? "border-emerald-500 bg-emerald-100 text-emerald-700" : password ? "border-rose-400 bg-rose-50 text-rose-600" : "border-slate-300 text-slate-400"
                      }`}
                    >
                      {ok ? "✓" : "•"}
                    </span>
                    <span>{rule.label}</span>
                  </li>
                );
              })}
            </ul>
            <p id="setup-password-validity" role={password && policyError ? "alert" : "status"} aria-live="polite" className={`pt-1 ${password && policyError ? "font-medium text-rose-700" : password ? "text-emerald-700" : "sr-only"}`}>
              {password ? (policyError ? `Password is invalid: ${policyError}` : "Password meets all requirements.") : "Enter a password to check its requirements."}
            </p>
          </div>

          <button
            type="submit"
            disabled={loading || Boolean(policyError) || Boolean(confirmError) || !token || linkInvalid || Boolean(success)}
            className="w-full portal-btn portal-btn-primary"
          >
            {loading ? "Saving..." : setupType === "invitation" ? "Complete Registration" : "Set Password"}
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
