// src/pages/EmployeePortal.tsx
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import ProjectForm, { type ProjectPayload } from "../../components/ProjectForm";
import ConfirmDialog from "../../components/ConfirmDialog";
import { api } from "../../services/api";

// Import your Projects and Reports components
import ProjectsPage from "./ProjectsPage";
import ReportsPage from "./ReportsPage";

type Row = {
  id: number;
  name: string;
  agency: string;
  status: "Planning" | "Proposed" | "Ongoing" | "Completed";
  budget: string;
  completion: number;
  createdAt: string;
  updatedAt: string;
};

const STORAGE_KEY = "rdc_freeze_mode_v1";

const PIPManagementSystem: React.FC = () => {
  const [activeSection, setActiveSection] = useState("dashboard");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [sortBy, setSortBy] = useState<
    "name" | "budget" | "completion" | "updated"
  >("updated");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");

  const [projects, setProjects] = useState<Row[]>([]);

  const [userRole, setUserRole] = useState<string | null>(() => {
    try {
      const u = localStorage.getItem("user");
      if (u) return JSON.parse(u).role;
    } catch (e) {}
    return null;
  });

  const roleClasses = (() => {
    switch (userRole) {
      case "admin":
        return {
          sidebar: "from-purple-900 via-purple-800 to-purple-900",
          accent: "bg-gradient-to-br from-purple-500 to-purple-600",
        };
      case "validator":
        return {
          sidebar: "from-blue-900 via-blue-800 to-blue-900",
          accent: "bg-gradient-to-br from-blue-500 to-blue-600",
        };
      default:
        return {
          sidebar: "from-green-900 via-green-800 to-green-900",
          accent: "bg-gradient-to-br from-green-500 to-green-600",
        };
    }
  })();

  const [freezeMode, setFreezeMode] = useState<boolean>(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : false;
  });

  const navigate = useNavigate();

  const apiToRow = (p: any): Row => ({
    id: p.id,
    name: p.title || p.name || "Untitled",
    agency: p.agency || "Unknown",
    status:
      p.status === "approved"
        ? "Completed"
        : p.status === "ongoing"
        ? "Ongoing"
        : p.status === "proposed" || p.status === "pending_validation"
        ? "Proposed"
        : "Planning",
    budget: `₱ ${Number(p.budget || 0).toLocaleString()}`,
    completion: p.completion ?? 0,
    createdAt: p.created_at || new Date().toISOString(),
    updatedAt: p.updated_at || new Date().toISOString(),
  });

  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Row | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [toDeleteId, setToDeleteId] = useState<number | null>(null);

  const [notification, setNotification] = useState<{
    message: string;
    type: "success" | "error" | "warning";
  } | null>(null);


  // Load projects from backend depending on role; 
  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        if (userRole === "employee") {
          const data = await api.get("employee/projects/");
          if (!cancelled)
            setProjects(Array.isArray(data) ? data.map(apiToRow) : []);
        } else if (userRole === "validator") {
          const data = await api.get("validator/projects/");
          if (!cancelled)
            setProjects(Array.isArray(data) ? data.map(apiToRow) : []);
        } else if (userRole === "admin") {
          const data = await api.get("admin/projects/");
          if (!cancelled)
            setProjects(Array.isArray(data) ? data.map(apiToRow) : []);
        } else {
          // no role or unauthenticated; do nothing (keep demo)
        }
      } catch (e) {
        console.warn("Could not load projects from API:", e);
        if (!cancelled) setProjects([]);
      }
    };

    load();
    const onStorage = (e: StorageEvent) => {
      if (e.key === "projects_last_update") {
        load();
      }
    };

    window.addEventListener("storage", onStorage);
    return () => {
      cancelled = true;
      window.removeEventListener("storage", onStorage);
    };
  }, [userRole]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(freezeMode));
  }, [freezeMode]);

  useEffect(() => {
    if (notification) {
      const timer = setTimeout(() => setNotification(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [notification]);

  const showNotification = (
    message: string,
    type: "success" | "error" | "warning"
  ) => {
    setNotification({ message, type });
  };

  const onAddClick = () => {
    if (freezeMode) {
      showNotification(
        "Project submissions are currently frozen by Admin.",
        "warning"
      );
      return;
    }
    if (userRole !== "employee") {
      showNotification("Only employees can add projects.", "error");
      return;
    }
    setEditing(null);
    setShowForm(true);
  };

  const onEditClick = (r: Row) => {
    if (freezeMode) {
      showNotification("System is frozen. Editing is restricted.", "warning");
      return;
    }
    // Only project owner (employee) or admin can edit in this simplified flow
    const user = localStorage.getItem("user");
    const current = user ? JSON.parse(user) : null;
    if (current?.role !== "admin" && current?.username !== r.name) {
      // note: in demo data we don't have submitted_by, so keep permissive for demo
      // But show a warning
      showNotification("You are not allowed to edit this project.", "error");
      return;
    }
    setEditing(r);
    setShowForm(true);
  };

  const onDeleteClick = (id: number) => {
    if (freezeMode) {
      showNotification("System is frozen. Deletion is restricted.", "warning");
      return;
    }
    setToDeleteId(id);
    setShowConfirm(true);
  };

  const handleSave = (payload: ProjectPayload) => {
    const timestamp = new Date().toISOString();

    const apiPayload = {
      title: payload.name,
      description: (payload as any).description || "",
      agency: payload.agency,
      budget: parseInt(payload.budget.replace(/[₱,\s]/g, "")) || 0,
      completion: payload.completion || 0,
      status:
        payload.status === "Completed"
          ? "approved"
          : payload.status === "Ongoing"
          ? "ongoing"
          : payload.status === "Proposed"
          ? "proposed"
          : "draft",
    };

    if (payload.id) {
      // Update local state
      setProjects((old) =>
        old.map((p) =>
          p.id === payload.id
            ? {
                ...p,
                name: payload.name,
                agency: payload.agency,
                status: payload.status,
                budget: payload.budget,
                completion: payload.completion,
                updatedAt: timestamp,
              }
            : p
        )
      );
      showNotification("Project updated successfully!", "success");
      (async () => {
        try {
          await api.put(`employee/projects/${payload.id}/`, apiPayload);
          // refresh list from API
          const list = await api.get("employee/projects/");
          setProjects(Array.isArray(list) ? list.map(apiToRow) : []);
          localStorage.setItem("projects_last_update", Date.now().toString());
        } catch (e) {
          console.warn("Failed to update project on API:", e);
          showNotification("Failed to update project.", "error");
        }
      })();
    } else {
      const newId = projects.length
        ? Math.max(...projects.map((p) => p.id)) + 1
        : 1;
      const newProject = {
        id: newId,
        name: payload.name,
        agency: payload.agency,
        status: payload.status,
        budget: payload.budget,
        completion: payload.completion,
        createdAt: timestamp,
        updatedAt: timestamp,
      } as Row;
      setProjects((old) => [newProject, ...old]);
      showNotification("New project added successfully!", "success");
      (async () => {
        try {
          await api.post("employee/projects/", apiPayload);
          const list = await api.get("employee/projects/");
          setProjects(Array.isArray(list) ? list.map(apiToRow) : []);
          localStorage.setItem("projects_last_update", Date.now().toString());
        } catch (e) {
          console.warn("Failed to create project on API:", e);
          showNotification("Failed to create project.", "error");
        }
      })();
    }
    setShowForm(false);
    setEditing(null);
  };

  const confirmDelete = () => {
    if (toDeleteId == null) {
      setShowConfirm(false);
      return;
    }
    setProjects((old) => old.filter((p) => p.id !== toDeleteId));
    showNotification("Project deleted successfully!", "success");
    (async () => {
      try {
        await api.del(`employee/projects/${toDeleteId}/`);
        const list = await api.get("employee/projects/");
        setProjects(Array.isArray(list) ? list.map(apiToRow) : []);
        localStorage.setItem("projects_last_update", Date.now().toString());
      } catch (e) {
        console.warn("Failed to delete project on API:", e);
        showNotification("Failed to delete project.", "error");
      }
    })();
    setToDeleteId(null);
    setShowConfirm(false);
  };

  const handleLogout = () => {
    localStorage.removeItem("user");
    localStorage.removeItem("isLoggedIn");
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    navigate("/login");
  };


  const filteredProjects = projects
    .filter((p) => {
      const matchesSearch =
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.agency.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesFilter = filterStatus === "all" || p.status === filterStatus;
      return matchesSearch && matchesFilter;
    })
    .sort((a, b) => {
      let comparison = 0;

      if (sortBy === "name") {
        comparison = a.name.localeCompare(b.name);
      } else if (sortBy === "budget") {
        const budgetA = parseInt(a.budget.replace(/[₱,\s]/g, ""));
        const budgetB = parseInt(b.budget.replace(/[₱,\s]/g, ""));
        comparison = budgetA - budgetB;
      } else if (sortBy === "completion") {
        comparison = a.completion - b.completion;
      } else if (sortBy === "updated") {
        comparison =
          new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime();
      }

      return sortOrder === "asc" ? comparison : -comparison;
    });

  const stats = {
    total: projects.length,
    totalBudget: projects.reduce((sum, p) => {
      const budget = parseInt(p.budget.replace(/[₱,\s]/g, ""));
      return sum + budget;
    }, 0),
    ongoing: projects.filter((p) => p.status === "Ongoing").length,
    completed: projects.filter((p) => p.status === "Completed").length,
    avgCompletion:
      projects.length > 0
        ? Math.round(
            projects.reduce((sum, p) => sum + p.completion, 0) / projects.length
          )
        : 0,
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex">
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      <aside
        className={`fixed lg:static inset-y-0 left-0 z-50 w-64 bg-gradient-to-b ${
          roleClasses.sidebar
        } text-white transform transition-transform duration-300 ease-in-out ${
          isSidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        } flex flex-col shadow-2xl`}
      >
        <div className="p-6 border-b border-blue-700 bg-blue-950 bg-opacity-50">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">RDIP-NCR</h1>
              <p className="text-xs text-blue-300 mt-1">Management Portal</p>
            </div>
            <button
              onClick={() => setIsSidebarOpen(false)}
              className="lg:hidden text-white hover:bg-blue-700 p-2 rounded-lg transition"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>
        </div>

        <nav className="flex-1 p-4 overflow-y-auto">
          <ul className="space-y-2">
            {[
              { id: "dashboard", label: "Dashboard" },
              { id: "projects", label: "Projects" },
              { id: "reports", label: "Reports" },
              { id: "directory", label: "Directory" },
              { id: "updates", label: "System Updates" },
            ].map((item) => (
              <li key={item.id}>
                <button
                  className={`w-full text-left px-4 py-3 rounded-lg transition-all duration-200 ${
                    activeSection === item.id
                      ? "bg-blue-700 shadow-lg font-semibold"
                      : "hover:bg-blue-700 hover:bg-opacity-50"
                  }`}
                  onClick={() => {
                    setActiveSection(item.id);
                    setIsSidebarOpen(false);
                  }}
                >
                  {item.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>

        <div className="p-4 border-t border-blue-700 bg-blue-950 bg-opacity-30">
          <div className="text-xs text-blue-200 space-y-1">
            <p>Last updated: Sept 11, 2025</p>
            <p>Version: 1.0.0</p>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white shadow-md z-30 sticky top-0">
          <div className="px-4 sm:px-6 py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setIsSidebarOpen(true)}
                  className="lg:hidden p-2 rounded-lg hover:bg-gray-100 transition"
                >
                  <svg
                    className="w-6 h-6"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M4 6h16M4 12h16M4 18h16"
                    />
                  </svg>
                </button>
                <div>
                  <h2 className={`text-lg sm:text-xl font-bold text-gray-800`}>
                    {activeSection === "dashboard" && "Dashboard"}
                    {activeSection === "projects" && "Project Management"}
                    {activeSection === "reports" && "Reports"}
                    {activeSection === "directory" && "Directory"}
                    {activeSection === "updates" && "System Updates"}
                  </h2>
                  <p className="text-xs sm:text-sm text-gray-600 hidden sm:block">
                    Monitoring and management of regional investment programs
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2 sm:gap-4">
                <div className="flex items-center gap-2">
                  <span className="text-xs sm:text-sm text-gray-600 hidden sm:inline">
                    Freeze
                  </span>
                  <button
                    onClick={() => setFreezeMode((v) => !v)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      freezeMode ? "bg-red-600" : "bg-green-600"
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        freezeMode ? "translate-x-6" : "translate-x-1"
                      }`}
                    />
                  </button>
                </div>

                <button
                  onClick={handleLogout}
                  className="px-3 py-2 bg-gray-200 text-gray-800 rounded-lg hover:bg-gray-300 transition text-sm font-medium"
                >
                  Logout
                </button>
              </div>
            </div>
          </div>

          {freezeMode && (
            <div className="bg-yellow-50 border-l-4 border-yellow-400 px-4 py-3">
              <p className="text-sm text-yellow-800 font-medium">
                ⚠️ Project submissions are currently frozen by Admin.
              </p>
            </div>
          )}
        </header>

        {notification && (
          <div className="fixed top-20 right-4 z-50 animate-slide-in">
            <div
              className={`rounded-lg shadow-lg p-4 flex items-center gap-3 ${
                notification.type === "success"
                  ? "bg-green-50 border-l-4 border-green-500"
                  : notification.type === "error"
                  ? "bg-red-50 border-l-4 border-red-500"
                  : "bg-yellow-50 border-l-4 border-yellow-500"
              }`}
            >
              <p className="text-sm font-medium text-gray-800">
                {notification.message}
              </p>
              <button onClick={() => setNotification(null)}>
                <svg
                  className="w-4 h-4 text-gray-500"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>
          </div>
        )}

        <main className="flex-1 overflow-y-auto p-4 sm:p-6">
          {/* DASHBOARD */}
          {activeSection === "dashboard" && (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl shadow-lg p-6 text-white">
                  <h3 className="text-sm font-medium opacity-90">
                    Total Projects
                  </h3>
                  <p className="text-4xl font-bold mt-2">{stats.total}</p>
                </div>
                <div className="bg-gradient-to-br from-green-500 to-green-600 rounded-xl shadow-lg p-6 text-white">
                  <h3 className="text-sm font-medium opacity-90">
                    Total Budget
                  </h3>
                  <p className="text-2xl font-bold mt-2">
                    ₱{stats.totalBudget.toLocaleString()}
                  </p>
                </div>
                <div className="bg-gradient-to-br from-yellow-500 to-yellow-600 rounded-xl shadow-lg p-6 text-white">
                  <h3 className="text-sm font-medium opacity-90">Ongoing</h3>
                  <p className="text-4xl font-bold mt-2">{stats.ongoing}</p>
                </div>
                <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl shadow-lg p-6 text-white">
                  <h3 className="text-sm font-medium opacity-90">
                    Avg Completion
                  </h3>
                  <p className="text-4xl font-bold mt-2">
                    {stats.avgCompletion}%
                  </p>
                </div>
              </div>

              <div className="bg-white rounded-xl shadow-lg overflow-hidden">
                <div className="p-4 sm:p-6 border-b border-gray-200">
                  <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                    <h3 className="text-xl font-bold text-gray-800">
                      Project Management
                    </h3>

                    <div className="flex flex-col sm:flex-row gap-3">
                      <input
                        type="text"
                        placeholder="Search projects..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 w-full sm:w-64"
                      />

                      <select
                        value={filterStatus}
                        onChange={(e) => setFilterStatus(e.target.value)}
                        className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="all">All Status</option>
                        <option value="Planning">Planning</option>
                        <option value="Proposed">Proposed</option>
                        <option value="Ongoing">Ongoing</option>
                        <option value="Completed">Completed</option>
                      </select>

                      <button
                        onClick={onAddClick}
                        disabled={freezeMode}
                        className={`px-4 py-2 rounded-lg font-medium transition-all ${
                          freezeMode
                            ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                            : "bg-blue-600 text-white hover:bg-blue-700"
                        }`}
                      >
                        Add Project
                      </button>

                    </div>
                  </div>

                  <div className="mt-4 text-sm text-gray-600">
                    Showing {filteredProjects.length} of {projects.length}{" "}
                    projects
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          Project Name
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          Agency
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          Status
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          Budget
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          Completion
                        </th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                          Actions
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {filteredProjects.map((project) => (
                        <tr
                          key={project.id}
                          className="hover:bg-gray-50 transition"
                        >
                          <td className="px-6 py-4">
                            <div className="text-sm font-medium text-gray-900">
                              {project.name}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="text-sm text-gray-500">
                              {project.agency}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <span
                              className={`px-2 py-1 text-xs font-semibold rounded-full ${
                                project.status === "Completed"
                                  ? "bg-green-100 text-green-800"
                                  : project.status === "Ongoing"
                                  ? "bg-yellow-100 text-yellow-800"
                                  : "bg-blue-100 text-blue-800"
                              }`}
                            >
                              {project.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-500">
                            {project.budget}
                          </td>
                          <td className="px-6 py-4">
                            <div className="w-full bg-gray-200 rounded-full h-2">
                              <div
                                className="h-2 rounded-full bg-blue-600"
                                style={{ width: `${project.completion}%` }}
                              />
                            </div>
                            <div className="text-xs text-gray-500 mt-1">
                              {project.completion}%
                            </div>
                          </td>
                          <td className="px-6 py-4 text-sm font-medium space-x-3">
                            {userRole === "validator" && (
                              <>
                                <button
                                  onClick={() => {
                                    // quick-approve action
                                    (async () => {
                                      try {
                                        await api.post(
                                          `validator/projects/${project.id}/validate/`,
                                          { action: "approve" }
                                        );
                                        showNotification(
                                          "Project approved",
                                          "success"
                                        );
                                      } catch (e) {
                                        showNotification(
                                          "Failed to validate project",
                                          "error"
                                        );
                                      }
                                    })();
                                  }}
                                  className="text-green-600 hover:text-green-900"
                                >
                                  Approve
                                </button>
                                <button
                                  onClick={() => {
                                    (async () => {
                                      try {
                                        await api.post(
                                          `validator/projects/${project.id}/validate/`,
                                          { action: "reject" }
                                        );
                                        showNotification(
                                          "Project rejected",
                                          "success"
                                        );
                                      } catch (e) {
                                        showNotification(
                                          "Failed to validate project",
                                          "error"
                                        );
                                      }
                                    })();
                                  }}
                                  className="text-red-600 hover:text-red-900"
                                >
                                  Reject
                                </button>
                              </>
                            )}

                            {userRole === "admin" && (
                              <>
                                <button
                                  onClick={() => {
                                    (async () => {
                                      try {
                                        await api.post(
                                          `admin/projects/${project.id}/archive/`
                                        );
                                        showNotification(
                                          "Project archived",
                                          "success"
                                        );
                                      } catch (e) {
                                        showNotification(
                                          "Failed to archive project",
                                          "error"
                                        );
                                      }
                                    })();
                                  }}
                                  className="text-yellow-600 hover:text-yellow-900"
                                >
                                  Archive
                                </button>
                              </>
                            )}

                            {userRole === "employee" && (
                              <>
                                <button
                                  onClick={() => onEditClick(project)}
                                  className="text-blue-600 hover:text-blue-900"
                                >
                                  Edit
                                </button>
                                <button
                                  onClick={() => onDeleteClick(project.id)}
                                  className="text-red-600 hover:text-red-900"
                                >
                                  Delete
                                </button>
                                <button
                                  onClick={() => {
                                    (async () => {
                                      try {
                                        await api.post(
                                          `employee/projects/${project.id}/submit/`
                                        );
                                        const list = await api.get(
                                          "employee/projects/"
                                        );
                                        setProjects(
                                          Array.isArray(list)
                                            ? list.map(apiToRow)
                                            : []
                                        );
                                        localStorage.setItem(
                                          "projects_last_update",
                                          Date.now().toString()
                                        );
                                        showNotification(
                                          "Project submitted",
                                          "success"
                                        );
                                      } catch (e) {
                                        showNotification(
                                          "Failed to submit project",
                                          "error"
                                        );
                                      }
                                    })();
                                  }}
                                  className="text-indigo-600 hover:text-indigo-900"
                                >
                                  Submit
                                </button>
                              </>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {/* PROJECTS PAGE */}
          {activeSection === "projects" && (
            <ProjectsPage />
          )}

          {/* REPORTS PAGE */}
          {activeSection === "reports" && <ReportsPage projects={projects} />}

          {/* PLACEHOLDER PAGES */}
          {activeSection === "directory" && (
            <div className="bg-white rounded-xl shadow-lg p-8 text-center">
              <h3 className="text-2xl font-bold text-gray-800">Directory</h3>
              <p className="text-gray-600 mt-2">
                Directory page coming soon...
              </p>
            </div>
          )}

          {activeSection === "updates" && (
            <div className="bg-white rounded-xl shadow-lg p-8 text-center">
              <h3 className="text-2xl font-bold text-gray-800">
                System Updates
              </h3>
              <p className="text-gray-600 mt-2">
                System Updates page coming soon...
              </p>
            </div>
          )}
        </main>
      </div>

      {showForm && (
        <ProjectForm
          initial={editing ?? undefined}
          onSave={(p) => handleSave(p as any)}
          onCancel={() => {
            setShowForm(false);
            setEditing(null);
          }}
        />
      )}
      {showConfirm && (
        <ConfirmDialog
          message="Are you sure you want to delete this project?"
          onCancel={() => {
            setShowConfirm(false);
            setToDeleteId(null);
          }}
          onConfirm={confirmDelete}
        />
      )}

      <style>{`
        @keyframes slide-in {
          from {
            transform: translateX(100%);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
        .animate-slide-in {
          animation: slide-in 0.3s ease-out;
        }
      `}</style>
    </div>
  );
};

export default PIPManagementSystem;



