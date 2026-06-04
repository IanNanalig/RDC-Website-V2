import React, { useEffect } from "react";
import { Navigate } from "react-router-dom";
import { api } from "../services/api";

interface ProtectedRouteProps {
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const isLoggedIn = localStorage.getItem("isLoggedIn") === "true";
  useEffect(() => {
    if (!isLoggedIn) {
      return;
    }

    let active = true;
    const verifySession = () => {
      api.get("auth/me/").catch(() => {
        // api.ts clears auth storage and redirects on replaced/expired sessions.
      });
    };

    verifySession();
    const onFocus = () => {
      if (active) {
        verifySession();
      }
    };
    window.addEventListener("focus", onFocus);

    return () => {
      active = false;
      window.removeEventListener("focus", onFocus);
    };
  }, [isLoggedIn]);

  return isLoggedIn ? <>{children}</> : <Navigate to="/login" replace />;
};

export default ProtectedRoute;
