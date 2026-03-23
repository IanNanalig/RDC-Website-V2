import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import { useEffect, useState } from "react";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import PublicChatbot from "./components/PublicChatbot";
import SafeBoundary from "./components/SafeBoundary";
import Home from "./pages/Home";
import NewsPage from "./pages/News";
import Publication from "./pages/Publication";
import AboutRDC from "./pages/About_RDC";
import Contact from "./pages/Contact";
import Projects from "./pages/Projects";
import ProjectDetails from "./pages/ProjectDetails";
import Login from "./pages/Login";
import Reports from "./pages/Reports";
import Directory from "./pages/Directory";
import Updates from "./pages/Updates";
import RegionalProfile from "./pages/RegionalProfile";
import RequestAccess from "./pages/RequestAccess";
import RequestPasswordReset from "./pages/RequestPasswordReset";
import SetupPassword from "./pages/SetupPassword";

// FIXED: Correct the import paths - it's "EmployesPortal" not "EmployeesPortal"
import Dashboard from "./pages/EmployesPortal/Dashboard";
import AdminDashboard from "./pages/EmployesPortal/AdminDashboard";
import ValidatorDashboard from "./pages/EmployesPortal/ValidatorDashboard";
import ValidatorReviewHistory from "./pages/EmployesPortal/ValidatorReviewHistory";
import ProjectsPage from "./pages/EmployesPortal/ProjectsPage";
import SimplifiedProjectSubmission from "./pages/EmployesPortal/SimplifiedProjectSubmission";
import ProjectReview from "./pages/EmployesPortal/ProjectReview";
import AdminProjects from "./pages/EmployesPortal/AdminProjects";
import AdminValidatorDiffs from "./pages/EmployesPortal/AdminValidatorDiffs";
import UserManagement from "./pages/EmployesPortal/UserManagement";

// Interface for user data
interface User {
  id: number;
  username: string;
  email: string;
  role: "admin" | "validator" | "employee";
  department?: string;
  position?: string;
}

// Protected Route Component with Role Checking
const ProtectedRoute = ({
  children,
  roles,
}: {
  children: React.ReactNode;
  roles?: ("admin" | "validator" | "employee")[];
}) => {
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);
  const location = useLocation();

  useEffect(() => {
    const checkAuth = () => {
      try {
        const userData = localStorage.getItem("user");
        const isLoggedIn = localStorage.getItem("isLoggedIn");

        console.log("ProtectedRoute - Checking auth:", {
          userData,
          isLoggedIn,
        });

        if (userData && isLoggedIn === "true") {
          const parsedUser: User = JSON.parse(userData);
          console.log("ProtectedRoute - Found user:", parsedUser);
          setUser(parsedUser);

          if (roles && !roles.includes(parsedUser.role)) {
            console.log(
              "ProtectedRoute - Wrong role:",
              parsedUser.role,
              "expected:",
              roles,
            );
          }
        } else {
          console.log("ProtectedRoute - No user data or not logged in");
          setUser(null);
        }
      } catch (error) {
        console.error("Error checking auth:", error);
        localStorage.removeItem("user");
        localStorage.removeItem("isLoggedIn");
        localStorage.removeItem("accessToken");
        localStorage.removeItem("refreshToken");
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, [location, roles]);

  if (loading) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (!user) {
    console.log("ProtectedRoute - No user, redirecting to login");
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // Check role permissions
  if (roles && !roles.includes(user.role)) {
    console.log(
      "ProtectedRoute - Wrong role, redirecting:",
      user.role,
      "expected:",
      roles,
    );
    let redirectPath = "/login";
    switch (user.role) {
      case "admin":
        redirectPath = "/admin/dashboard";
        break;
      case "validator":
        redirectPath = "/validator/dashboard";
        break;
      case "employee":
        redirectPath = "/employee/dashboard";
        break;
    }
    return <Navigate to={redirectPath} replace />;
  }

  console.log("ProtectedRoute - Access granted for:", user.role);
  return <>{children}</>;
};

// Higher-order component to conditionally wrap with Navbar AND Footer (for PUBLIC pages)
const withLayout = (Component: React.ComponentType) => {
  return () => (
    <>
      <Navbar />
      <Component />
      <Footer />
      <SafeBoundary>
        <PublicChatbot />
      </SafeBoundary>
    </>
  );
};

// Higher-order component for pages with ONLY Navbar (no Footer) - PUBLIC pages
const withNavbarOnly = (Component: React.ComponentType) => {
  return () => (
    <>
      <Navbar />
      <Component />
      <SafeBoundary>
        <PublicChatbot />
      </SafeBoundary>
    </>
  );
};

// Wrapper component for Employee Portal pages with PortalHeader
const PortalPageWrapper = ({
  children,
  pageTitle,
}: {
  children: React.ReactNode;
  pageTitle: string;
}) => {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    const userData = localStorage.getItem("user");
    if (userData) {
      setUser(JSON.parse(userData));
    }
  }, []);

  if (!user) {
    return (
      <div className="flex justify-center items-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" data-page-title={pageTitle}>
      {children}
    </div>
  );
};

// PUBLIC Pages (with main Navbar)
const HomeWithLayout = withLayout(Home);
const AboutWithLayout = withLayout(AboutRDC);
const NewsWithLayout = withLayout(NewsPage);
const PublicationWithLayout = withLayout(Publication);
const ProjectDetailsWithLayout = withLayout(ProjectDetails);
const RegionalProfileWithLayout = withLayout(RegionalProfile);
const ContactWithNavbarOnly = withNavbarOnly(Contact);
const ProjectsWithNavbarOnly = withNavbarOnly(Projects);

// EMPLOYEE PORTAL Pages (with PortalHeader)
const DashboardPage = () => (
  <PortalPageWrapper pageTitle="Employee Dashboard">
    <Dashboard />
  </PortalPageWrapper>
);

const AdminDashboardPage = () => (
  <PortalPageWrapper pageTitle="Admin Dashboard">
    <AdminDashboard />
  </PortalPageWrapper>
);

const ValidatorDashboardPage = () => (
  <PortalPageWrapper pageTitle="Validator Dashboard">
    <ValidatorDashboard />
  </PortalPageWrapper>
);

const ValidatorReviewHistoryPage = () => (
  <PortalPageWrapper pageTitle="Reviewed & Endorsed">
    <ValidatorReviewHistory />
  </PortalPageWrapper>
);

const ProjectsPageComponent = () => (
  <PortalPageWrapper pageTitle="Projects">
    <ProjectsPage />
  </PortalPageWrapper>
);

const SimplifiedProjectSubmissionPage = () => (
  <PortalPageWrapper pageTitle="Simplified Project Submission">
    <SimplifiedProjectSubmission />
  </PortalPageWrapper>
);

const ProjectReviewPage = () => (
  <PortalPageWrapper pageTitle="Project Review">
    <ProjectReview />
  </PortalPageWrapper>
);

const AdminProjectsPage = () => (
  <PortalPageWrapper pageTitle="Admin Projects">
    <AdminProjects />
  </PortalPageWrapper>
);

const AdminValidatorDiffsPage = () => (
        <PortalPageWrapper pageTitle="Validator Tracker">
    <AdminValidatorDiffs />
  </PortalPageWrapper>
);

const UserManagementPage = () => (
  <PortalPageWrapper pageTitle="User Management">
    <UserManagement />
  </PortalPageWrapper>
);

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ===== PUBLIC ROUTES (with main Navbar) ===== */}
        <Route path="/" element={<HomeWithLayout />} />
        <Route path="/about" element={<AboutWithLayout />} />
        <Route path="/news" element={<NewsWithLayout />} />
        <Route path="/news/:slug" element={<NewsWithLayout />} />
        <Route path="/publications" element={<PublicationWithLayout />} />
        <Route path="/projects" element={<ProjectsWithNavbarOnly />} />
        <Route path="/projects/:id" element={<ProjectDetailsWithLayout />} />
        <Route
          path="/regional-profile"
          element={<RegionalProfileWithLayout />}
        />
        <Route path="/documents" element={<PublicationWithLayout />} />
        <Route path="/documents/:id" element={<ProjectsWithNavbarOnly />} />
        <Route path="/contact" element={<ContactWithNavbarOnly />} />
        <Route path="/login" element={<Login />} />
        <Route path="/request-password-reset" element={<RequestPasswordReset />} />
        <Route path="/setup-password" element={<SetupPassword />} />
        <Route path="/request-access" element={<RequestAccess />} />

        {/* ===== EMPLOYEE PORTAL ROUTES (with PortalHeader) ===== */}
        <Route
          path="/employee/dashboard"
          element={
            <ProtectedRoute roles={["employee"]}>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employee/projects"
          element={
            <ProtectedRoute roles={["employee"]}>
              <ProjectsPageComponent />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employee/projects/new"
          element={
            <ProtectedRoute roles={["employee"]}>
              <SimplifiedProjectSubmissionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employee/projects/new/simplified"
          element={
            <ProtectedRoute roles={["employee"]}>
              <SimplifiedProjectSubmissionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employee/projects/:id/edit"
          element={
            <ProtectedRoute roles={["employee"]}>
              <SimplifiedProjectSubmissionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employee/projects/:id/edit/simplified"
          element={
            <ProtectedRoute roles={["employee"]}>
              <SimplifiedProjectSubmissionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employee/projects/:id/view"
          element={
            <ProtectedRoute roles={["employee"]}>
              <ProjectReviewPage />
            </ProtectedRoute>
          }
        />

        {/* ===== VALIDATOR PORTAL ROUTES (with PortalHeader) ===== */}
        <Route
          path="/validator/dashboard"
          element={
            <ProtectedRoute roles={["validator"]}>
              <ValidatorDashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/validator/projects"
          element={
            <ProtectedRoute roles={["validator"]}>
              <ProjectsPageComponent />
            </ProtectedRoute>
          }
        />
        <Route
          path="/validator/projects/history"
          element={
            <ProtectedRoute roles={["validator"]}>
              <ValidatorReviewHistoryPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/validator/projects/:id/review"
          element={
            <ProtectedRoute roles={["validator"]}>
              <SimplifiedProjectSubmissionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/validator/projects/:id/review/simplified"
          element={
            <ProtectedRoute roles={["validator"]}>
              <SimplifiedProjectSubmissionPage />
            </ProtectedRoute>
          }
        />

        {/* ===== ADMIN PORTAL ROUTES (with PortalHeader) ===== */}
        <Route
          path="/admin/dashboard"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminDashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/projects"
          element={
            <ProtectedRoute roles={["admin"]}>
              <ProjectsPageComponent />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/validator-diffs"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminValidatorDiffsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/projects/:id/review"
          element={
            <ProtectedRoute roles={["admin"]}>
              <ProjectReviewPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/projects/:id/view"
          element={
            <ProtectedRoute roles={["admin"]}>
              <SimplifiedProjectSubmissionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/projects/:id/view/simplified"
          element={
            <ProtectedRoute roles={["admin"]}>
              <SimplifiedProjectSubmissionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/users"
          element={
            <ProtectedRoute roles={["admin"]}>
              <UserManagementPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin/archived"
          element={
            <ProtectedRoute roles={["admin"]}>
              <AdminProjectsPage />
            </ProtectedRoute>
          }
        />

        {/* ===== LEGACY & REDIRECT ROUTES ===== */}
        <Route
          path="/EmployesPortal"
          element={<Navigate to="/redirect-by-role" replace />}
        />
        <Route path="/redirect-by-role" element={<RoleRedirect />} />

        {/* ===== PROTECTED PUBLIC ROUTES (Reports, Directory, Updates) ===== */}
        <Route
          path="/reports"
          element={
            <ProtectedRoute>
              <Navbar />
              <Reports />
              <Footer />
              <SafeBoundary>
                <PublicChatbot />
              </SafeBoundary>
            </ProtectedRoute>
          }
        />
        <Route
          path="/directory"
          element={
            <ProtectedRoute>
              <Navbar />
              <Directory />
              <Footer />
              <SafeBoundary>
                <PublicChatbot />
              </SafeBoundary>
            </ProtectedRoute>
          }
        />
        <Route
          path="/updates"
          element={
            <ProtectedRoute>
              <Navbar />
              <Updates />
              <Footer />
              <SafeBoundary>
                <PublicChatbot />
              </SafeBoundary>
            </ProtectedRoute>
          }
        />

        {/* ===== CATCH-ALL ROUTE ===== */}
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </BrowserRouter>
  );
}

// Component to redirect users based on their role
function RoleRedirect() {
  useEffect(() => {
    const userData = localStorage.getItem("user");
    console.log("RoleRedirect - User data:", userData);

    if (userData) {
      try {
        const user = JSON.parse(userData);
        console.log("RoleRedirect - Parsed user:", user);

        let redirectPath = "/login";
        switch (user.role) {
          case "admin":
            redirectPath = "/admin/dashboard";
            break;
          case "validator":
            redirectPath = "/validator/dashboard";
            break;
          case "employee":
            redirectPath = "/employee/dashboard";
            break;
        }

        console.log("RoleRedirect - Redirecting to:", redirectPath);
        window.location.href = redirectPath;
      } catch (error) {
        console.error("RoleRedirect - Error parsing user:", error);
        window.location.href = "/login";
      }
    } else {
      console.log("RoleRedirect - No user data, redirecting to login");
      window.location.href = "/login";
    }
  }, []);

  return (
    <div className="flex justify-center items-center min-h-screen">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p className="text-gray-600">Redirecting to your dashboard...</p>
      </div>
    </div>
  );
}
