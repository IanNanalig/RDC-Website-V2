import React, { useState } from "react";
import { useNavigate, Link, useLocation } from "react-router-dom";
import photo1 from "../assets/Photo-Corousel/Photos/photo1.jpg";
import rdcLogo from "../assets/Photo-Corousel/Photos/RDC-NCR LOGO.png";
import { API_BASE_URL } from "../config/api";

const Login: React.FC = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      let res = await fetch(`${API_BASE_URL}/auth/login/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.detail || "Invalid email or password");
      }

      const user = data.user;
      localStorage.setItem("accessToken", data.access);
      localStorage.setItem("refreshToken", data.refresh);
      localStorage.setItem("user", JSON.stringify(user));
      localStorage.setItem("isLoggedIn", "true");
      localStorage.setItem("username", user.username);

      const from = (location.state as any)?.from?.pathname || "/";
      switch (user.role) {
        case "admin":
          navigate("/admin/dashboard", { replace: true });
          break;
        case "validator":
          navigate("/validator/dashboard", { replace: true });
          break;
        case "employee":
          navigate("/employee/dashboard", { replace: true });
          break;
        default:
          navigate(from, { replace: true });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen overflow-hidden relative">
      {/* Background Image */}
      <div
        className="absolute inset-0 z-0"
        style={{
          backgroundImage: `url(${photo1})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
          backgroundRepeat: "no-repeat",
          filter: "brightness(1.15) saturate(1.2) contrast(1.05)",
        }}
      >
        <div className="absolute inset-0 bg-white/10"></div>
        <div
          className="absolute inset-0 opacity-3"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23000000' fill-opacity='0.03'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }}
        ></div>
      </div>

      {/* Back to Home Button */}
      <Link
        to="/"
        className="absolute top-8 left-8 z-30 flex items-center gap-2 text-gray-800 hover:text-blue-700 transition-all duration-300 group bg-white/90 hover:bg-white px-4 py-2 rounded-lg border border-gray-300 shadow-sm"
      >
        <svg
          className="w-4 h-4 group-hover:-translate-x-1 transition-transform"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M10 19l-7-7m0 0l7-7m-7 7h18"
          />
        </svg>
        <span className="font-medium">Back to Home</span>
      </Link>

      {/* Main Login Container */}
      <div className="relative z-10 min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-sm">
          {/* Logo/Header Section */}
          <div className="text-center mb-10 animate-fade-in">
            <div className="flex justify-center mb-5">
              <div className="w-24 h-24 flex items-center justify-center">
                <img
                  src={rdcLogo}
                  alt="RDC-NCR Logo"
                  className="w-full h-full object-contain drop-shadow-sm"
                />
              </div>
            </div>
            <h1 className="text-3xl font-bold text-gray-800 mb-3 tracking-tight">
              RDC-NCR Portal
            </h1>
            <p className="text-gray-600 text-lg">
              Regional Development Council - National Capital Region
            </p>
          </div>

          {/* Login Card */}
          <div className="bg-white/80 backdrop-blur-sm shadow-lg rounded-xl p-6 animate-slide-up border border-white/40">
            {/* Error Message */}
            {error && (
              <div className="mb-4 p-3 bg-red-50/90 border border-red-200 rounded-lg animate-shake">
                <div className="flex items-center gap-2">
                  <div className="w-5 h-5 bg-red-100 rounded-full flex items-center justify-center flex-shrink-0">
                    <svg
                      className="w-3 h-3 text-red-500"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                    >
                      <path
                        fillRule="evenodd"
                        d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                        clipRule="evenodd"
                      />
                    </svg>
                  </div>
                  <p className="text-red-600 text-xs">{error}</p>
                </div>
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-4">
              {/* Username Field */}
              <div>
                <label className="block text-gray-700 text-sm font-medium mb-1">
                  Email
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    setError("");
                  }}
                  className="w-full px-3 py-2.5 bg-white/95 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100 transition placeholder-gray-400 text-gray-800"
                  placeholder="Enter email"
                  required
                  autoFocus
                  autoComplete="email"
                />
              </div>

              {/* Password Field */}
              <div>
                <label className="block text-gray-700 text-sm font-medium mb-1">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPass ? "text" : "password"}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                      setError("");
                    }}
                    className="w-full px-3 py-2.5 bg-white/95 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100 transition placeholder-gray-400 text-gray-800"
                    placeholder="Enter password"
                    required
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPass(!showPass)}
                    className="absolute right-2 top-1/2 transform -translate-y-1/2 p-1 text-gray-500 hover:text-blue-600 transition-colors"
                    aria-label={showPass ? "Hide password" : "Show password"}
                  >
                    {showPass ? (
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M13.875 18.825A10.05 10.05 0 0112 19c-4.5 0-8.25-3-9.5-7 1.25-4 5-7 9.5-7 1.657 0 3.216.41 4.563 1.125M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M3 3l18 18"
                        />
                      </svg>
                    ) : (
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                        />
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                        />
                      </svg>
                    )}
                  </button>
                </div>
              </div>

              {/* Remember Me & Forgot Password */}
              <div className="flex items-center justify-between pt-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    className="w-3.5 h-3.5 text-blue-500 rounded border-gray-300 focus:ring-blue-200"
                  />
                  <span className="text-xs text-gray-600">Remember me</span>
                </label>
                <Link
                  to="/forgot-password"
                  className="text-xs text-blue-600 hover:text-blue-800 transition-colors"
                >
                  Forgot password?
                </Link>
              </div>

              {/* Login Button */}
              <button
                type="submit"
                disabled={loading}
                className={`w-full py-2.5 px-4 rounded-lg font-medium text-sm transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-300 relative ${
                  loading
                    ? "bg-blue-400 cursor-not-allowed"
                    : "bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700"
                } text-white shadow hover:shadow-md`}
              >
                <div className="flex items-center justify-center gap-2">
                  {loading ? (
                    <>
                      <svg
                        className="w-4 h-4 animate-spin"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                      <span>Authenticating...</span>
                    </>
                  ) : (
                    <>
                      <span>Login to RDC Portal</span>
                      <svg
                        className="w-3.5 h-3.5"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"
                        />
                      </svg>
                    </>
                  )}
                </div>
              </button>
            </form>

            {/* Simple Footer */}
            <div className="mt-6 pt-4 border-t border-gray-200/70 text-center">
              <p className="text-xs text-gray-500 mt-1">
                Trouble signing in?{" "}
                <Link
                  to="/request-password-reset"
                  className="text-blue-600 hover:text-blue-800 font-medium transition-colors"
                >
                  Request a password reset
                </Link>
              </p>
              <p className="text-xs text-gray-500 mt-1">
                v1.0.0 • RDC-NCR Portal System
              </p>
            </div>
          </div>
        </div>
      </div>

      <style>
        {`
        @keyframes fadeIn {
          0% { opacity: 0; }
          100% { opacity: 1; }
        }
        
        @keyframes slideUp {
          0% { opacity: 0; transform: translateY(20px); }
          100% { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          10%, 30%, 50%, 70%, 90% { transform: translateX(-2px); }
          20%, 40%, 60%, 80% { transform: translateX(2px); }
        }
        
        .animate-fade-in {
          animation: fadeIn 0.8s ease-out;
        }
        
        .animate-slide-up {
          animation: slideUp 0.5s ease-out;
        }
        
        .animate-shake {
          animation: shake 0.3s ease-in-out;
        }
        `}
      </style>
    </div>
  );
};

export default Login;
