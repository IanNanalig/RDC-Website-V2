import { Link, useLocation } from "react-router-dom";
import { useState, useEffect } from "react";
import rdcLogo from "../assets/Photo-Corousel/Photos/RDC-NCR LOGO.png";

const navLinks = [
  { to: "/", label: "Home" },
  { to: "/regional-profile", label: "RegionProfile" },
  { to: "/documents", label: "Publications" },
  { to: "/projects", label: "Dashboard" },
  { to: "/news", label: "News" },
  { to: "/about", label: "About RDC" },
  { to: "/contact", label: "Contact Us" },
];

const Navbar: React.FC = () => {
  const location = useLocation();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());

  // Update time every second
  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000); // Update every second

    return () => clearInterval(timer);
  }, []);

  const toggleMobileMenu = () => {
    setIsMobileMenuOpen(!isMobileMenuOpen);
  };

  // Format time for display with seconds
  const formatTime = (date: Date) => {
    return date.toLocaleString("en-PH", {
      timeZone: "Asia/Manila",
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  return (
    <>
      {/* Header Bar (single source of logo/title) */}
      <div className="bg-green-600 text-white py-3">
        <div className="container mx-auto px-4 flex justify-between items-center">
          <div className="flex items-center gap-4">
            {/* Updated logo container without white background */}
            <div className="w-16 h-16 sm:w-20 sm:h-20 flex items-center justify-center flex-shrink-0">
              <img
                src={rdcLogo}
                alt="RDC Logo"
                className="w-full h-full object-contain"
              />
            </div>
            <div>
              <p className="text-xs sm:text-sm font-semibold">
                Republic of the Philippines
              </p>
              <h1 className="text-base sm:text-xl font-bold">
                Regional Development Council
              </h1>
              <p className="text-xs sm:text-sm">National Capital Region</p>
            </div>
          </div>
          <div className="text-right hidden md:block">
            <p className="text-sm">Philippine Standard Time:</p>
            <p className="text-lg font-semibold">{formatTime(currentTime)}</p>
          </div>
        </div>
      </div>

      {/* Navigation (no duplicate logo/title, login removed) */}
      <nav className="bg-green-700">
        <div className="container mx-auto px-4 py-3 flex items-center">
          {/* Left spacer aligns nav with header logo */}
          <div className="hidden md:block w-16" />

          {/* Desktop Navigation */}
          <ul className="hidden lg:flex space-x-8 flex-1">
            {navLinks.map((link) => (
              <li key={link.to}>
                <Link
                  to={link.to}
                  className={`font-semibold transition-colors duration-200 ${
                    location.pathname === link.to
                      ? "text-white border-b-2 border-white"
                      : "text-white/90 hover:text-white"
                  }`}
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>

          {/* Right side: only mobile toggle (login removed) */}
          <div className="flex items-center gap-3 ml-auto">
            <button
              onClick={toggleMobileMenu}
              className="lg:hidden text-white hover:text-gray-200 focus:outline-none"
              aria-label={isMobileMenuOpen ? "Close menu" : "Open menu"}
            >
              {isMobileMenuOpen ? (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              ) : (
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 8h16M4 16h16"
                  />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Menu (login entry removed) */}
        <div
          className={`lg:hidden overflow-hidden transition-all duration-300 ease-in-out ${
            isMobileMenuOpen ? "max-h-96 border-t border-gray-200" : "max-h-0"
          }`}
        >
          <ul className="flex flex-col py-4 space-y-2">
            {navLinks.map((link) => (
              <li key={link.to}>
                <Link
                  to={link.to}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`block px-4 py-2 rounded-md transition-all duration-200 ${
                    location.pathname === link.to
                      ? "bg-white text-green-700 font-bold border-l-4 border-green-700"
                      : "text-white hover:bg-white/10"
                  }`}
                >
                  {link.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </nav>
    </>
  );
};

export default Navbar;
