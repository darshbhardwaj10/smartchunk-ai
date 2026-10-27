export function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

export function errorMessage(error) {
  return error instanceof Error ? error.message : "An unexpected error occurred.";
}

export function downloadJson(filename, data) {
  downloadBlob(filename, JSON.stringify(data, null, 2), "application/json;charset=utf-8");
}

export function downloadJsonl(filename, rows) {
  const content = rows.map((row) => JSON.stringify(row)).join("\n");
  downloadBlob(filename, `${content}${content ? "\n" : ""}`, "application/x-ndjson;charset=utf-8");
}

function downloadBlob(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
