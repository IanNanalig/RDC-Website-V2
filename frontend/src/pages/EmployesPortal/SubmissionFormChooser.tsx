import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import PortalLayout from "../../components/portal/PortalLayout";
import { useEncodingWindow } from "../../hooks/useEncodingWindow";

type StoredUser = {
  username?: string;
  full_name?: string;
};

const getStoredUser = (): StoredUser | null => {
  try {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

export default function SubmissionFormChooser() {
  const navigate = useNavigate();
  const encodingWindow = useEncodingWindow(true);
  const user = useMemo(getStoredUser, []);
  const displayName = user?.full_name || user?.username || "User";
  const canEncode = encodingWindow.can_encode;

  if (!encodingWindow.loading && !canEncode) {
    return (
      <PortalLayout
        title="Choose Submission Form"
        subtitle="Select the form format required for your project entry"
        role="employee"
        userName={displayName}
        topActions={
          <button type="button" onClick={() => navigate("/employee/projects")} className="portal-btn portal-btn-ghost">
            Back to Projects
          </button>
        }
      >
        <div className="portal-card p-4 border-amber-200 bg-amber-50 text-amber-800">
          {encodingWindow.message || "Contributor encoding is currently closed. You may still view your projects."}
        </div>
      </PortalLayout>
    );
  }

  return (
    <PortalLayout
      title="Choose Submission Form"
      subtitle="Select the form format required for your project entry"
      role="employee"
      userName={displayName}
      topActions={
        <button type="button" onClick={() => navigate("/employee/projects")} className="portal-btn portal-btn-ghost">
          Back to Projects
        </button>
      }
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="portal-card overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-base font-semibold text-slate-900">Simplified Form (RDIP)</h2>
          </div>
          <div className="portal-card-body space-y-4">
            <p className="text-sm text-slate-600">
              Use this for the streamlined RDIP monitoring matrix format (program/project, funding rows, status flags).
            </p>
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
              <li>Faster encoding for agencies/LGUs</li>
              <li>Includes RDIP-specific dropdown structure</li>
              <li>Supports validator RDIP category tracking</li>
            </ul>
            <button
              type="button"
              onClick={() => navigate("/employee/projects/new/simplified")}
              className="portal-btn portal-btn-primary"
              disabled={encodingWindow.loading}
            >
              Use Simplified Form
            </button>
          </div>
        </section>

        <section className="portal-card overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3">
            <h2 className="text-base font-semibold text-slate-900">Detailed Form (RDIP)</h2>
          </div>
          <div className="portal-card-body space-y-4">
            <p className="text-sm text-slate-600">
              Use this for the full detailed project profile with all sections and comprehensive planning fields.
            </p>
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
              <li>Full template with multi-step sections</li>
              <li>Detailed planning and implementation metadata</li>
              <li>Best for complete PAP documentation</li>
            </ul>
            <button
              type="button"
              onClick={() => navigate("/employee/projects/new/detailed")}
              className="portal-btn portal-btn-primary"
              disabled={encodingWindow.loading}
            >
              Use Detailed Form
            </button>
          </div>
        </section>
      </div>
    </PortalLayout>
  );
}
