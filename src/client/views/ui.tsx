export function StatusBadge({ status }: { status: string }) {
  const tone =
    ["completed", "approved", "ALLOW", "ok"].includes(status) ? "ok" :
    ["awaiting_approval", "pending", "queued", "running", "generating", "draft", "PENDING"].includes(status) ? "warn" :
    ["denied", "stopped", "failed", "expired", "DENY", "STOP"].includes(status) ? "danger" : "info";
  return <span className={`badge ${tone}`}>{status.replace(/_/g, " ")}</span>;
}

export function formatTime(value: number | string | null | undefined) {
  if (!value) return "—";
  const date = new Date(Number(value));
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
