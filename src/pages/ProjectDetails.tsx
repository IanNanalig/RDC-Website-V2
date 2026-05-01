// src/pages/ProjectDetails.tsx
import React, { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getPublicProject, type PublicProject as Project } from "../services/publicProjectsApi";

const money = (n: number) => `₱ ${n.toLocaleString()}`;

const ProjectDetails: React.FC = () => {
  const { id } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const run = async () => {
      const pid = Number(id);
      if (!pid) {
        setProject(null);
        setLoading(false);
        return;
      }
      try {
        const data = await getPublicProject(pid);
        setProject(data);
      } catch {
        setProject(null);
      } finally {
        setLoading(false);
      }
    };
    run();
  }, [id]);

  if (loading) {
    return <div className="p-8">Loading...</div>;
  }

  if (!project)
    return (
      <div className="p-8">
        Project not found.{" "}
        <Link to="/projects" className="text-blue-600">
          Back to Projects
        </Link>
      </div>
    );

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <Link to="/projects" className="text-blue-600 mb-4 inline-block">
        ← Back to Projects
      </Link>
      <div className="bg-white rounded shadow p-6">
        <h1 className="text-2xl font-bold text-blue-900">{project.title}</h1>
        <div className="flex gap-4 items-center mt-3">
          <span className="px-3 py-1 rounded-full bg-gray-100 text-sm">
            {project.agency}
          </span>
          <span className="px-3 py-1 rounded-full bg-gray-100 text-sm">
            {project.lgu || "Unspecified"}
          </span>
          <span className="px-3 py-1 rounded-full bg-green-50 text-sm">
            {project.implementation_status || "Unspecified"}
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
          <div className="p-4 border rounded">
            <div className="text-sm text-gray-500">Budget</div>
            <div className="text-lg font-semibold">{money(project.budget)}</div>
          </div>
          <div className="p-4 border rounded">
            <div className="text-sm text-gray-500">Start Year</div>
            <div className="text-lg">{project.year ?? "—"}</div>
          </div>
          <div className="p-4 border rounded">
            <div className="text-sm text-gray-500">Updated</div>
            <div className="text-lg">
              {project.updated_at ? new Date(project.updated_at).toLocaleDateString() : "—"}
            </div>
          </div>
        </div>

        <div className="mt-6 text-gray-700">
          <h3 className="font-semibold mb-2">Description</h3>
          <p>{project.description}</p>
        </div>

        <div className="mt-6 text-gray-700 text-sm">
          <h3 className="font-semibold mb-2">Documents</h3>
          <p>Documents are not available on the public dashboard for this project.</p>
        </div>
      </div>
    </div>
  );
};

export default ProjectDetails;
