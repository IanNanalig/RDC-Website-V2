import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from "react-router-dom";
import { lazy, Suspense, useEffect, useState } from "react";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";
import PublicChatbot from "./components/PublicChatbot";
import SafeBoundary from "./components/SafeBoundary";

const Home = lazy(() => import("./pages/Home"));
const NewsPage = lazy(() => import("./pages/News"));
const Publication = lazy(() => import("./pages/Publication"));
const AboutRDC = lazy(() => import("./pages/About_RDC"));
const Contact = lazy(() => import("./pages/Contact"));
const Projects = lazy(() => import("./pages/Projects"));
const ProjectDetails = lazy(() => import("./pages/ProjectDetails"));
const Login = lazy(() => import("./pages/Login"));
const Reports = lazy(() => import("./pages/Reports"));
const Directory = lazy(() => import("./pages/Directory"));
const Updates = lazy(() => import("./pages/Updates"));
const RegionalProfile = lazy(() => import("./pages/RegionalProfile"));
const RequestAccess = lazy(() => import("./pages/RequestAccess"));
const RequestPasswordReset = lazy(() => import("./pages/RequestPasswordReset"));
const SetupPassword = lazy(() => import("./pages/SetupPassword"));

const Dashboard = lazy(() => import("./pages/EmployesPortal/Dashboard"));
const AdminDashboard = lazy(() => import("./pages/EmployesPortal/AdminDashboard"));
const ValidatorDashboard = lazy(() => import("./pages/EmployesPortal/ValidatorDashboard"));
const ValidatorReviewHistory = lazy(() => import("./pages/EmployesPortal/ValidatorReviewHistory"));
const ProjectsPage = lazy(() => import("./pages/EmployesPortal/ProjectsPage"));
const SubmissionFormChooser = lazy(() => import("./pages/EmployesPortal/SubmissionFormChooser"));
const SimplifiedProjectSubmission = lazy(() => import("./pages/EmployesPortal/SimplifiedProjectSubmission"));
const ProjectSubmission = lazy(() => import("./pages/EmployesPortal/ProjectSubmission"));
const ProjectReview = lazy(() => import("./pages/EmployesPortal/ProjectReview"));
const AdminProjects = lazy(() => import("./pages/EmployesPortal/AdminProjects"));
const AdminValidatorDiffs = lazy(() => import("./pages/EmployesPortal/AdminValidatorDiffs"));
const UserManagement = lazy(() => import("./pages/EmployesPortal/UserManagement"));
const ContentManagement = lazy(() => import("./pages/EmployesPortal/ContentManagement"));

// Interface for user data
interface User {
  id: number;
  username: string;
  email: string;
  role: "admin" | "validator" | "employee" | "content_editor";
  agency?: string | null;
  department?: string;
  position?: string;
}

const RouteLoading = () => (
  <div className="flex min-h-screen items-center justify-center bg-slate-50">
    <div className="text-center">
      <div className="mx-auto mb-4 h-12 w-12 animate-spin rounded-full border-b-2 border-t-2 border-blue-500" />
      <p className="text-sm font-medium text-slate-600">Loading page...</p>
    </div>
  </div>
);

// Protected Route Component with Role Checking
const ProtectedRoute = ({
  children,
  roles,
}: {
  children: React.ReactNode;
  roles?: ("admin" | "validator" | "employee" | "content_editor")[];
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
      case "content_editor":
        redirectPath = "/content/dashboard";
        break;
    }
    return <Navigate to={redirectPath} replace />;
  }

  console.log("ProtectedRoute - Access granted for:", user.role);
  return <>{children}</>;
};

// Higher-order component to conditionally wrap with Navbar AND Footer (for PUBLIC pages)
const withLayout = (Component: React.ElementType) => {
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
const withNavbarOnly = (Component: React.ElementType) => {
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

const SubmissionFormChooserPage = () => (
  <PortalPageWrapper pageTitle="Choose Submission Form">
    <SubmissionFormChooser />
  </PortalPageWrapper>
);

const SimplifiedProjectSubmissionPage = () => (
  <PortalPageWrapper pageTitle="Simplified Project Submission">
    <SimplifiedProjectSubmission />
  </PortalPageWrapper>
);

const ProjectSubmissionPage = () => (
  <PortalPageWrapper pageTitle="Detailed Project Submission">
    <ProjectSubmission />
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

const ContentManagementPage = () => (
  <PortalPageWrapper pageTitle="Content Management">
    <ContentManagement />
  </PortalPageWrapper>
);

export default function App() {
  return (
    <BrowserRouter>
      <Suspense fallback={<RouteLoading />}>
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
              <SubmissionFormChooserPage />
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
          path="/employee/projects/new/detailed"
          element={
            <ProtectedRoute roles={["employee"]}>
              <ProjectSubmissionPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/employee/projects/:id/edit"
          element={
            <ProtectedRoute roles={["employee"]}>
              <ProjectSubmissionPage />
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
              <ProjectSubmissionPage />
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
              <ProjectSubmissionPage />
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
          path="/admin/content"
          element={
            <ProtectedRoute roles={["admin"]}>
              <ContentManagementPage />
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

        {/* ===== CONTENT EDITOR PORTAL ROUTES ===== */}
        <Route
          path="/content/dashboard"
          element={
            <ProtectedRoute roles={["content_editor"]}>
              <ContentManagementPage />
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
      </Suspense>
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
          case "content_editor":
            redirectPath = "/content/dashboard";
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
