type RefreshButtonProps = {
  loading: boolean;
  onClick: () => void | Promise<unknown>;
  label?: string;
  className?: string;
  disabled?: boolean;
};

export default function RefreshButton({
  loading,
  onClick,
  label = "Refresh",
  className = "portal-btn portal-btn-ghost",
  disabled = false,
}: RefreshButtonProps) {
  return (
    <button
      type="button"
      aria-busy={loading}
      disabled={disabled}
      onClick={() => { void onClick(); }}
      className={className}
    >
      {loading ? "Refreshing..." : label}
    </button>
  );
}
