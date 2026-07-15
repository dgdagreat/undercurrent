// Thin fetch wrapper around the FastAPI backend. Vite proxies /api to :8000.

export async function fetchBusinesses() {
  const res = await fetch("/api/businesses");
  if (!res.ok) throw new Error("Failed to load businesses");
  return res.json();
}

export async function fetchBusiness(id) {
  const res = await fetch(`/api/businesses/${id}`);
  if (!res.ok) throw new Error("Failed to load business");
  return res.json();
}
