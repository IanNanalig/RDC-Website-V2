import React from "react";
import { useNavigate } from "react-router-dom";
import PortalLayout from "../../components/portal/PortalLayout";

const SubmissionTypeChooser: React.FC = () => {
  const navigate = useNavigate();
  const userRaw = localStorage.getItem("user");
  const user = userRaw
    ? JSON.parse(userRaw)
    : { username: "employee", role: "employee" };

  return (
    <PortalLayout
      title="Choose Submission Form"
      subtitle="Select the form format required for your project entry"
      role="employee"
      userName={user.username}
      topActions={
        <button
          type="button"
          onClick={() => navigate("/employee/projects")}
          className="portal-btn portal-btn-ghost"
        >
          Back to Projects
        </button>
      }
    >
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="portal-card">
          <div className="portal-card-header">
            <h2 className="text-lg font-semibold">Simplified Form (RDIP)</h2>
          </div>
          <div className="portal-card-body space-y-3">
            <p className="text-sm text-slate-600">
              Use this for the streamlined RDIP monitoring matrix format
              (program/project, funding rows, status flags).
            </p>
            <ul className="text-sm text-slate-700 list-disc pl-5 space-y-1">
              <li>Faster encoding for agencies/LGUs</li>
              <li>Includes RDIP-specific dropdown structure</li>
              <li>Supports validator RDIP category tracking</li>
            </ul>
            <button
              type="button"
              onClick={() => navigate("/employee/projects/new/simplified")}
              className="portal-btn portal-btn-primary"
            >
              Use Simplified Form
            </button>
          </div>
        </div>

        <div className="portal-card">
          <div className="portal-card-header">
            <h2 className="text-lg font-semibold">Detailed Form (RDIP)</h2>
          </div>
          <div className="portal-card-body space-y-3">
            <p className="text-sm text-slate-600">
              Use this for the full detailed project profile with all sections
              and comprehensive planning fields.
            </p>
            <ul className="text-sm text-slate-700 list-disc pl-5 space-y-1">
              <li>Full template with multi-step sections</li>
              <li>Detailed planning and implementation metadata</li>
              <li>Best for complete PAP documentation</li>
            </ul>
            <button
              type="button"
              onClick={() => navigate("/employee/projects/new/detailed")}
              className="portal-btn portal-btn-primary"
            >
              Use Detailed Form
            </button>
          </div>
        </div>
      </div>
    </PortalLayout>
  );
};

export default SubmissionTypeChooser;
