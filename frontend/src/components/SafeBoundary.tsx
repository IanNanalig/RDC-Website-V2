import React from "react";

type SafeBoundaryProps = {
  children: React.ReactNode;
  fallback?: React.ReactNode;
};

type SafeBoundaryState = {
  hasError: boolean;
};

class SafeBoundary extends React.Component<SafeBoundaryProps, SafeBoundaryState> {
  state: SafeBoundaryState = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    console.error("SafeBoundary caught error:", error);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? null;
    }
    return this.props.children;
  }
}

export default SafeBoundary;
