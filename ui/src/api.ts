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
  name: "organize" | "analyze";
  state: "running" | "done" | "error";
  phase: string;
  done: number;
  total: number;
  error: string | null;
  // organize jobs return album info; analyze jobs return analysis counts
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
  | { type: "unsorted" }
  | { type: "search"; q: string }
  | { type: "cleanup" };

export type AnalysisStatus = { total: number; embedded: number; measured: number; pending: number };

export type CleanupImage = ImageItem & { sharpness: number | null; brightness: number | null };

export type DuplicateGroup = { kind: "exact" | "similar"; keep_id: number; images: CleanupImage[]; reclaimable: number };

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

  exportTemplateFields: () => request<Record<string, string>>("/api/export/template-fields"),
  exportPreview: (dest: string, includeUnsorted: boolean, template: string) =>
    post<ExportPreview>("/api/export/preview", { dest, include_unsorted: includeUnsorted, template }),
  exportApply: (dest: string, includeUnsorted: boolean, template: string) =>
    post<ExportResult>("/api/export/apply", { dest, include_unsorted: includeUnsorted, template }),
  exportUndo: (id: number) => post<{ removed: number; kept: number }>(`/api/export/${id}/undo`),

  analysisStatus: () => request<AnalysisStatus>("/api/analysis"),
  analyze: () => post<Job>("/api/analysis"),
  search: (q: string) =>
    request<AnalysisStatus & { items: (ImageItem & { score: number })[]; searched: number }>(
      `/api/search?${new URLSearchParams({ q })}`,
    ),

  duplicates: () => request<{ groups: DuplicateGroup[]; reclaimable: number }>("/api/cleanup/duplicates"),
  blurry: (threshold: number) => request<{ items: CleanupImage[] }>(`/api/cleanup/blurry?threshold=${threshold}`),
  dark: (threshold: number) => request<{ items: CleanupImage[] }>(`/api/cleanup/dark?threshold=${threshold}`),
  keep: (imageIds: number[]) => post("/api/cleanup/keep", { image_ids: imageIds }),
  trash: (imageIds: number[]) =>
    post<{ trashed: number; freed: number; failed: { path: string; error: string }[] }>("/api/cleanup/trash", {
      image_ids: imageIds,
    }),
};

/** Drag-and-drop payload type for moving photos onto albums. */
export const DRAG_TYPE = "application/x-sortified-images";

export const formatBytes = (bytes: number) =>
  bytes > 1e9 ? `${(bytes / 1e9).toFixed(2)} GB` : bytes > 1e6 ? `${(bytes / 1e6).toFixed(1)} MB` : `${Math.round(bytes / 1e3)} KB`;
