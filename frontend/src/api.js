// Thin fetch wrapper around the FastAPI backend. Vite proxies /api to :8000.

export async function fetchBusinesses() {
  const res = await fetch("/api/businesses");
  if (!res.ok) throw new Error("Failed to load businesses");
  return res.json();
}

export async function fetchBusiness(id) {
  const res = await fetch(`/api/businesses/${id}`);
  if (!res.ok) {
    const err = new Error("Failed to load business");
    err.status = res.status; // let callers distinguish 404 from a transient error
    throw err;
  }
  return res.json();
}

// Upload a transactions CSV. `fields` = { file, name, industry, openingBalance }.
// On a validation problem the backend replies 4xx with a human-readable
// `detail` — surface that verbatim so the user can fix their file.
export async function uploadBusiness({ file, name, industry, openingBalance }) {
  const form = new FormData();
  form.append("file", file);
  form.append("name", name);
  if (industry) form.append("industry", industry);
  if (openingBalance !== "" && openingBalance != null)
    form.append("opening_balance", openingBalance);

  const res = await fetch("/api/uploads", { method: "POST", body: form });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(body?.detail || "Upload failed");
  return body;
}

// Recompute a business's score under hypothetical adjustments (read-only on the
// server). Pass an AbortController signal so rapid slider drags cancel stale
// in-flight requests. Returns { baseline, adjusted, cashflow }.
export async function simulateWhatIf(id, params, signal) {
  const res = await fetch(`/api/businesses/${id}/whatif`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
    signal,
  });
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new Error(body?.detail || "Simulation failed");
  return body;
}

export async function deleteBusiness(id) {
  const res = await fetch(`/api/businesses/${id}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || "Delete failed");
  }
}

// The trained ML model's default-risk second opinion. Returns null if the model
// isn't trained (503) so the UI can simply hide the panel.
export async function fetchMlPrediction(id) {
  const res = await fetch(`/api/businesses/${id}/ml`);
  if (res.status === 503 || res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to load ML prediction");
  return res.json();
}
