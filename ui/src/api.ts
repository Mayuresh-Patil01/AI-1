// Small typed wrapper around the Python engine's API.
// All requests go to /api/..., which Vite forwards to http://127.0.0.1:8000.

export type Folder = { id: number; path: string; image_count: number };

export type ImageItem = {
  id: number;
  folder_id: number;
  path: string;
  name: string;
  size: number;
  width: number | null;
  height: number | null;
  taken_at: string | null;
};

export type ScanResult = { added: number; updated: number; unchanged: number; removed: number };

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}

export const api = {
  health: () => request<{ status: string; version: string }>("/api/health"),
  folders: () => request<Folder[]>("/api/folders"),
  addFolder: (path: string) =>
    request<{ id: number; path: string; scan: ScanResult }>("/api/folders", {
      method: "POST",
      body: JSON.stringify({ path }),
    }),
  rescan: (id: number) => request<ScanResult>(`/api/folders/${id}/rescan`, { method: "POST" }),
  removeFolder: (id: number) => request(`/api/folders/${id}`, { method: "DELETE" }),
  images: (folderId: number | null, offset = 0, limit = 200) => {
    const q = new URLSearchParams({ offset: String(offset), limit: String(limit) });
    if (folderId) q.set("folder_id", String(folderId));
    return request<{ total: number; items: ImageItem[] }>(`/api/images?${q}`);
  },
  thumbnailUrl: (id: number, size: "thumb" | "large" = "thumb") => `/api/images/${id}/thumbnail?size=${size}`,
};
