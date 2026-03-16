import React from "react";
import { Link } from "react-router-dom";

const RequestAccess: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4">
      <div className="max-w-2xl mx-auto bg-white rounded-xl shadow p-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Request Portal Access</h1>
        <p className="text-sm text-gray-600 mb-6">
          Access requests are currently disabled. Please contact the RDC Portal administrator for an account.
        </p>

        <div className="flex items-center gap-3 pt-2">
          <Link to="/login" className="px-4 py-2 rounded-lg border">
            Back to Login
          </Link>
        </div>
      </div>
    </div>
  );
};

export default RequestAccess;
