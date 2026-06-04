import React from "react";

interface PortalHeaderProps {
  title: string;
  userRole: "admin" | "validator" | "employee";
  userName: string;
}

const PortalHeader: React.FC<PortalHeaderProps> = ({
  title,
  userRole,
  userName,
}) => {
  const getRoleColor = (role: string) => {
    switch (role) {
      case "admin":
        return "bg-purple-100 text-purple-800";
      case "validator":
        return "bg-blue-100 text-blue-800";
      case "employee":
        return "bg-green-100 text-green-800";
      default:
        return "bg-gray-100 text-gray-800";
    }
  };

  const handleLogout = () => {
    // Clear all authentication data
    localStorage.removeItem("user");
    localStorage.removeItem("isLoggedIn");
    localStorage.removeItem("username");
    localStorage.removeItem("token");
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");

    // Force reload to clear any state
    window.location.href = "/login";
  };

  const getDashboardTitle = () => {
    switch (userRole) {
      case "admin":
        return "Admin Portal";
      case "validator":
        return "Validator Portal";
      case "employee":
        return "Employee Portal";
      default:
        return "Portal";
    }
  };

  return (
    <header className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Left side - Logo and Navigation */}
          <div className="flex items-center space-x-4">
            {/* Title */}
            <div className="hidden md:block">
              <h1 className="text-xl font-semibold text-gray-900">
                {getDashboardTitle()}
              </h1>
              <p className="text-sm text-gray-600">{title}</p>
            </div>
          </div>

          {/* Right side - User info and actions */}
          <div className="flex items-center space-x-4">
            {/* User Info */}
            <div className="hidden md:flex items-center space-x-3">
              <div className="text-right">
                <span className="text-sm font-medium text-gray-900">
                  {userName}
                </span>
                <div className="flex items-center space-x-2">
                  <span
                    className={`text-xs px-2 py-1 rounded-full ${getRoleColor(
                      userRole
                    )}`}
                  >
                    {userRole.charAt(0).toUpperCase() + userRole.slice(1)}
                  </span>
                </div>
              </div>

              {/* User Avatar */}
              <div className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center">
                <span className="text-sm font-medium text-gray-600">
                  {userName.charAt(0).toUpperCase()}
                </span>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center space-x-2">
              {/* Logout Button */}
              <button
                onClick={handleLogout}
                className="flex items-center space-x-2 px-3 py-2 bg-red-50 text-red-700 hover:bg-red-100 rounded-lg transition-colors"
                title="Logout"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                  />
                </svg>
                <span className="text-sm font-medium hidden md:inline">
                  Logout
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Mobile Title */}
        <div className="md:hidden py-4 border-t">
          <h1 className="text-lg font-semibold text-gray-900">
            {getDashboardTitle()}
          </h1>
          <p className="text-sm text-gray-600">{title}</p>
        </div>
      </div>
    </header>
  );
};

export default PortalHeader;
