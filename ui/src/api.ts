// Small typed wrapper around the Python engine's API.
// All requests go to /api/..., which Vite forwards to http://127.0.0.1:8000.

export type Folder = { id: number; path: string; image_count: number };

export type ImageItem = {
  id: number;
  folder_id: number;
  album_id: number | null;
  path: string;
  name: string;
  size: number;
  width: number | null;
  height: number | null;
  taken_at: string | null;
};

export type Album = { id: number; name: string; kind: string; count: number; cover_id: number | null };

export type ScanResult = { added: number; updated: number; unchanged: number; removed: number };

export type Job = {
  id: number;
  name: string;
  state: "running" | "done" | "error";
  phase: string;
  done: number;
  total: number;
  error: string | null;
  result: { analyzed: number; placed: number; unsorted: number; albums: { name: string; count: number }[] } | null;
};

export type OrganizeOptions =
  | { mode: "auto"; count: number | null }
  | { mode: "custom"; categories: string[]; strictness: number };

export type ExportPreview = {
  dest: string;
  total: number;
  bytes: number;
  folders: { name: string; count: number }[];
  sample: { src: string; dst: string }[];
};

export type ExportResult = { id: number; dest: string; copied: number; failed: { src: string; error: string }[] };

/** What the main area is showing. */
export type View =
  | { type: "all" }
  | { type: "folder"; id: number }
  | { type: "album"; id: number }
  | { type: "unsorted" };

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const detail = Array.isArray(body.detail) ? body.detail[0]?.msg : body.detail;
    throw new Error(detail ?? `Request failed (${res.status})`);
  }
  return res.json();
}

const post = <T>(url: string, body?: unknown) =>
  request<T>(url, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  health: () => request<{ status: string; version: string }>("/api/health"),

  folders: () => request<Folder[]>("/api/folders"),
  addFolder: (path: string) => post<{ id: number; path: string; scan: ScanResult }>("/api/folders", { path }),
  rescan: (id: number) => post<ScanResult>(`/api/folders/${id}/rescan`),
  removeFolder: (id: number) => request(`/api/folders/${id}`, { method: "DELETE" }),

  images: (view: View, offset = 0, limit = 200) => {
    const q = new URLSearchParams({ offset: String(offset), limit: String(limit) });
    if (view.type === "folder") q.set("folder_id", String(view.id));
    if (view.type === "album") q.set("album_id", String(view.id));
    if (view.type === "unsorted") q.set("unsorted", "true");
    return request<{ total: number; items: ImageItem[] }>(`/api/images?${q}`);
  },
  thumbnailUrl: (id: number, size: "thumb" | "large" = "thumb") => `/api/images/${id}/thumbnail?size=${size}`,

  organize: (opts: OrganizeOptions) => post<Job>("/api/organize", opts),
  currentJob: () => request<Job | null>("/api/jobs/current"),

  albums: () => request<{ albums: Album[]; unsorted: number }>("/api/albums"),
  createAlbum: (name: string) => post<{ id: number; name: string }>("/api/albums", { name }),
  renameAlbum: (id: number, name: string) =>
    request(`/api/albums/${id}`, { method: "PATCH", body: JSON.stringify({ name }) }),
  deleteAlbum: (id: number) => request(`/api/albums/${id}`, { method: "DELETE" }),
  moveToAlbum: (albumId: number, imageIds: number[]) => post(`/api/albums/${albumId}/images`, { image_ids: imageIds }),
  unassign: (imageIds: number[]) => post("/api/albums/unassign", { image_ids: imageIds }),

  exportPreview: (dest: string, includeUnsorted: boolean) =>
    post<ExportPreview>("/api/export/preview", { dest, include_unsorted: includeUnsorted }),
  exportApply: (dest: string, includeUnsorted: boolean) =>
    post<ExportResult>("/api/export/apply", { dest, include_unsorted: includeUnsorted }),
  exportUndo: (id: number) => post<{ removed: number; kept: number }>(`/api/export/${id}/undo`),
};

/** Drag-and-drop payload type for moving photos onto albums. */
export const DRAG_TYPE = "application/x-sortified-images";

export const formatBytes = (bytes: number) =>
  bytes > 1e9 ? `${(bytes / 1e9).toFixed(2)} GB` : bytes > 1e6 ? `${(bytes / 1e6).toFixed(1)} MB` : `${Math.round(bytes / 1e3)} KB`;
