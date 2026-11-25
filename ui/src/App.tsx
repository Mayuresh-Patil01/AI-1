import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, FolderOutput, ImageOff, Loader2, Pencil, Trash2, X } from "lucide-react";
import { api, type Album, type Folder, type ImageItem, type View } from "./api";
import Sidebar from "./components/Sidebar";
import PhotoGrid from "./components/PhotoGrid";
import Lightbox from "./components/Lightbox";
import OrganizeDialog from "./components/OrganizeDialog";
import ExportDialog from "./components/ExportDialog";
import SearchBar from "./components/SearchBar";
import CleanupView from "./components/CleanupView";
import AnalysisBanner from "./components/AnalysisBanner";
import Modal, { GhostButton, PrimaryButton } from "./components/Modal";

const PAGE = 200;

export default function App() {
  const [engineOk, setEngineOk] = useState<boolean | null>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [albums, setAlbums] = useState<Album[]>([]);
  const [unsorted, setUnsorted] = useState(0);
  const [view, setView] = useState<View>({ type: "all" });
  const [images, setImages] = useState<ImageItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [lastClicked, setLastClicked] = useState<number | null>(null);
  const [lightbox, setLightbox] = useState<number | null>(null);
  const [dialog, setDialog] = useState<"organize" | "export" | "newAlbum" | null>(null);
  const [toast, setToast] = useState<{ text: string; error?: boolean } | null>(null);

  const notify = useCallback((text: string, error = false) => {
    setToast({ text, error });
    setTimeout(() => setToast(null), 3500);
  }, []);

  const loadFolders = useCallback(async () => setFolders(await api.folders()), []);
  const loadAlbums = useCallback(async () => {
    const res = await api.albums();
    setAlbums(res.albums);
    setUnsorted(res.unsorted);
  }, []);

  const loadImages = useCallback(async (v: View) => {
    if (v.type === "cleanup") return; // Cleanup loads its own data
    if (v.type === "search") {
      // Don't show the previous view's count while a search is running.
      setImages([]);
      setTotal(0);
    }
    setLoading(true);
    try {
      const res = v.type === "search" ? await api.search(v.q) : await api.images(v, 0, PAGE);
      setImages(res.items);
      setTotal(v.type === "search" ? res.items.length : (res as { total: number }).total);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setLoading(false);
    }
  }, [notify]);

  /** Reload everything that may have changed, keeping the current view. */
  const refresh = useCallback(async () => {
    await Promise.all([loadFolders(), loadAlbums()]);
    await loadImages(view);
  }, [loadFolders, loadAlbums, loadImages, view]);

  // On startup: check the engine is running, then load the library.
  useEffect(() => {
    api
      .health()
      .then(() => {
        setEngineOk(true);
        return Promise.all([loadFolders(), loadAlbums()]);
      })
      .catch(() => setEngineOk(false));
  }, [loadFolders, loadAlbums]);

  // Whenever the view changes: load its photos and clear the selection.
  useEffect(() => {
    if (!engineOk) return;
    setSelected(new Set());
    loadImages(view);
  }, [engineOk, view, loadImages]);

  // Esc clears the selection.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !dialog && lightbox === null && setSelected(new Set());
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dialog, lightbox]);

  async function loadMore() {
    const res = await api.images(view, images.length, PAGE);
    setImages((prev) => [...prev, ...res.items]);
  }

  function toggle(id: number, range: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (range && lastClicked !== null) {
        // Shift-click selects everything between the last clicked photo and this one.
        const a = images.findIndex((i) => i.id === lastClicked);
        const b = images.findIndex((i) => i.id === id);
        images.slice(Math.min(a, b), Math.max(a, b) + 1).forEach((i) => next.add(i.id));
      } else if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setLastClicked(id);
  }

  // ---------- actions ----------

  async function handleAdd(path: string) {
    try {
      const res = await api.addFolder(path);
      notify(`Found ${res.scan.added.toLocaleString()} new photos`);
      await Promise.all([loadFolders(), loadAlbums()]);
      setView({ type: "folder", id: res.id });
    } catch (e) {
      notify((e as Error).message, true);
    }
  }

  async function handleRescan(id: number) {
    const r = await api.rescan(id);
    notify(`Rescan: +${r.added} new, ${r.updated} changed, ${r.removed} gone`);
    await refresh();
  }

  async function handleRemove(id: number) {
    await api.removeFolder(id);
    notify("Folder removed from library (files untouched)");
    if (view.type === "folder" && view.id === id) setView({ type: "all" });
    else await refresh();
    await Promise.all([loadFolders(), loadAlbums()]);
  }

  async function moveImages(albumId: number | null, ids: number[]) {
    if (!ids.length) return;
    try {
      if (albumId === null) await api.unassign(ids);
      else await api.moveToAlbum(albumId, ids);
      const where = albumId === null ? "Unsorted" : albums.find((a) => a.id === albumId)?.name;
      notify(`Moved ${ids.length} photo${ids.length > 1 ? "s" : ""} to ${where}`);
      setSelected(new Set());
      await refresh();
    } catch (e) {
      notify((e as Error).message, true);
    }
  }

  async function renameAlbum(id: number, name: string) {
    await api.renameAlbum(id, name);
    await loadAlbums();
  }

  async function deleteAlbum(id: number) {
    const album = albums.find((a) => a.id === id);
    if (!album || !confirm(`Delete album "${album.name}"? Its ${album.count} photos go back to Unsorted. No files are deleted.`)) return;
    await api.deleteAlbum(id);
    notify(`Deleted album "${album.name}"`);
    await loadAlbums();
    setView({ type: "unsorted" });
  }

  async function createAlbum(name: string) {
    const a = await api.createAlbum(name);
    if (selected.size) await api.moveToAlbum(a.id, [...selected]);
    setDialog(null);
    await loadAlbums();
    setView({ type: "album", id: a.id });
  }

  const onOrganized = useCallback(() => {
    loadAlbums();
    loadImages(view);
  }, [loadAlbums, loadImages, view]);

  // ---------- render ----------

  if (engineOk === false) return <EngineOffline />;

  const currentAlbum = view.type === "album" ? albums.find((a) => a.id === view.id) : undefined;
  const currentFolder = view.type === "folder" ? folders.find((f) => f.id === view.id) : undefined;
  const title =
    view.type === "all" ? "All photos"
    : view.type === "unsorted" ? "Unsorted"
    : view.type === "search" ? `“${view.q}”`
    : view.type === "cleanup" ? "Cleanup"
    : currentAlbum?.name ?? currentFolder?.path.split(/[\\/]/).pop() ?? "";
  const subtitle =
    view.type === "search" ? `${total.toLocaleString()} matching photo${total === 1 ? "" : "s"}, best matches first`
    : view.type === "cleanup" ? "Find duplicates, blurry and dark photos. Nothing is deleted without asking"
    : `${total.toLocaleString()} photo${total === 1 ? "" : "s"}`;

  return (
    <div className="flex h-full">
      <Sidebar
        folders={folders}
        albums={albums}
        unsorted={unsorted}
        view={view}
        onView={setView}
        onAdd={handleAdd}
        onRescan={handleRescan}
        onRemove={handleRemove}
        onOrganize={() => setDialog("organize")}
        onNewAlbum={() => setDialog("newAlbum")}
        onDrop={moveImages}
      />

      <main className="flex-1 overflow-y-auto">
        <header className="sticky top-0 z-10 flex items-center gap-4 border-b border-ink-700/60 bg-ink-950/80 px-8 py-5 backdrop-blur">
          <div className="min-w-0 flex-1">
            {currentAlbum ? (
              <EditableTitle key={currentAlbum.id} value={currentAlbum.name} onSave={(n) => renameAlbum(currentAlbum.id, n)} />
            ) : (
              <h2 className="truncate font-display text-2xl font-semibold">{title}</h2>
            )}
            <p className="mt-0.5 truncate text-sm text-ink-400">
              {subtitle}
              {currentFolder && <span className="ml-2 text-ink-600">{currentFolder.path}</span>}
              {view.type === "unsorted" && <span className="ml-2 text-ink-600">Photos not in any album</span>}
              {currentAlbum && <span className="ml-2 text-ink-600">Drag photos onto an album in the sidebar to move them</span>}
            </p>
          </div>
          {folders.length > 0 && (
            <SearchBar
              value={view.type === "search" ? view.q : ""}
              onSearch={(q) => setView({ type: "search", q })}
              onClear={() => view.type === "search" && setView({ type: "all" })}
            />
          )}
          {currentAlbum && (
            <GhostButton onClick={() => deleteAlbum(currentAlbum.id)} title="Delete album (photos go to Unsorted)">
              <Trash2 className="size-4" />
            </GhostButton>
          )}
          {albums.length > 0 && (
            <PrimaryButton onClick={() => setDialog("export")}>
              <FolderOutput className="size-4" /> Export
            </PrimaryButton>
          )}
        </header>

        <div className="p-8">
          {view.type === "search" && <AnalysisBanner what="search results" onDone={() => loadImages(view)} />}
          {view.type === "cleanup" ? (
            <CleanupView notify={notify} onChanged={() => Promise.all([loadFolders(), loadAlbums()])} />
          ) : loading || engineOk === null ? (
            <div className="flex justify-center py-24 text-ink-400">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : images.length === 0 ? (
            <EmptyState view={view} hasFolders={folders.length > 0} />
          ) : (
            <>
              <PhotoGrid images={images} selected={selected} onToggle={toggle} onOpen={setLightbox} />
              {images.length < total && (
                <div className="mt-8 flex justify-center">
                  <GhostButton onClick={loadMore}>Load more ({(total - images.length).toLocaleString()} left)</GhostButton>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {selected.size > 0 && (
        <SelectionBar
          count={selected.size}
          albums={albums}
          inAlbum={view.type === "album"}
          onMove={(albumId) => moveImages(albumId, [...selected])}
          onNewAlbum={() => setDialog("newAlbum")}
          onClear={() => setSelected(new Set())}
        />
      )}

      {lightbox !== null && <Lightbox images={images} index={lightbox} onIndex={setLightbox} onClose={() => setLightbox(null)} />}
      {dialog === "organize" && <OrganizeDialog hasAlbums={albums.length > 0} onClose={() => setDialog(null)} onFinished={onOrganized} />}
      {dialog === "export" && <ExportDialog onClose={() => setDialog(null)} />}
      {dialog === "newAlbum" && <NewAlbumDialog withSelection={selected.size} onCreate={createAlbum} onClose={() => setDialog(null)} />}

      {toast && (
        <div
          className={`fixed right-6 bottom-6 z-50 rounded-xl px-4 py-3 text-sm shadow-xl animate-fade-up ${
            toast.error ? "bg-red-500/90 text-white" : "bg-ink-700 text-ink-100 ring-1 ring-ink-600"
          }`}
        >
          {toast.text}
        </div>
      )}
    </div>
  );
}

function SelectionBar(props: {
  count: number;
  albums: Album[];
  inAlbum: boolean;
  onMove: (albumId: number | null) => void;
  onNewAlbum: () => void;
  onClear: () => void;
}) {
  return (
    <div className="fixed bottom-6 left-1/2 z-30 flex -translate-x-1/2 items-center gap-3 rounded-2xl bg-ink-800/95 py-2 pr-2 pl-5 shadow-2xl ring-1 ring-ink-600 backdrop-blur animate-fade-up">
      <span className="text-sm font-medium">{props.count} selected</span>
      <select
        value=""
        onChange={(e) => {
          const v = e.target.value;
          if (v === "new") props.onNewAlbum();
          else if (v) props.onMove(v === "unsorted" ? null : Number(v));
        }}
        className="rounded-lg bg-ink-700 px-3 py-1.5 text-sm ring-1 ring-ink-600 focus:outline-none"
      >
        <option value="">Move to album…</option>
        {props.albums.map((a) => (
          <option key={a.id} value={a.id}>
            {a.name}
          </option>
        ))}
        <option value="new">+ New album…</option>
        {props.inAlbum && <option value="unsorted">Remove from album</option>}
      </select>
      <button onClick={props.onClear} title="Clear selection (Esc)" className="rounded-lg p-2 text-ink-400 hover:bg-ink-700 hover:text-white">
        <X className="size-4" />
      </button>
    </div>
  );
}

function EditableTitle({ value, onSave }: { value: string; onSave: (v: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value);
  const save = () => {
    setEditing(false);
    if (text.trim() && text.trim() !== value) onSave(text.trim());
    else setText(value);
  };
  return editing ? (
    <input
      autoFocus
      value={text}
      onChange={(e) => setText(e.target.value)}
      onBlur={save}
      onKeyDown={(e) => {
        if (e.key === "Enter") save();
        if (e.key === "Escape") {
          setText(value);
          setEditing(false);
        }
      }}
      className="w-full max-w-md rounded-md bg-ink-800 px-2 font-display text-2xl font-semibold ring-1 ring-brand-400 focus:outline-none"
    />
  ) : (
    <button onClick={() => setEditing(true)} className="group flex max-w-full items-center gap-2" title="Rename album">
      <h2 className="truncate font-display text-2xl font-semibold">{value}</h2>
      <Pencil className="size-4 shrink-0 text-ink-600 group-hover:text-ink-300" />
    </button>
  );
}

function NewAlbumDialog({ withSelection, onCreate, onClose }: { withSelection: number; onCreate: (name: string) => void; onClose: () => void }) {
  const [name, setName] = useState("");
  return (
    <Modal title="New album" subtitle={withSelection ? `The ${withSelection} selected photos will be moved into it.` : undefined} onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) onCreate(name.trim());
        }}
      >
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Goa Trip 2025"
          className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm placeholder:text-ink-400 focus:border-brand-400 focus:outline-none"
        />
        <div className="mt-5 flex justify-end gap-2">
          <GhostButton type="button" onClick={onClose}>Cancel</GhostButton>
          <PrimaryButton type="submit" disabled={!name.trim()}>Create</PrimaryButton>
        </div>
      </form>
    </Modal>
  );
}

function EmptyState({ view, hasFolders }: { view: View; hasFolders: boolean }) {
  const [heading, text] =
    !hasFolders ? ["Your library is empty", "Paste a folder path in the sidebar to start. SORTIFIED only reads your photos. It never changes them without asking."]
    : view.type === "album" ? ["This album is empty", "Drag photos onto it in the sidebar, or select photos and use “Move to album”."]
    : view.type === "unsorted" ? ["Everything is sorted 🎉", "Every photo is in an album."]
    : view.type === "search" ? ["No matches", "Try describing it differently, e.g. “people smiling outdoors” or “handwritten notes”."]
    : ["No photos here", "This folder has no supported images (JPG, PNG, WEBP, HEIC…)."];
  return (
    <div className="flex flex-col items-center py-24 text-center">
      <div className="mb-5 rounded-2xl bg-ink-800 p-5 ring-1 ring-ink-700">
        <ImageOff className="size-8 text-brand-400" />
      </div>
      <h3 className="font-display text-xl font-semibold">{heading}</h3>
      <p className="mt-2 max-w-sm text-sm text-ink-400">{text}</p>
    </div>
  );
}

function EngineOffline() {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <div className="max-w-lg rounded-2xl bg-ink-900 p-8 ring-1 ring-ink-700">
        <div className="flex items-center gap-3 text-amber-400">
          <AlertTriangle className="size-5" />
          <h2 className="font-display text-lg font-semibold">The SORTIFIED engine isn't running</h2>
        </div>
        <p className="mt-3 text-sm text-ink-300">Start it in a terminal, then refresh this page:</p>
        <pre className="mt-3 overflow-x-auto rounded-lg bg-ink-950 p-4 text-xs text-ink-100">
          cd engine{"\n"}.venv\Scripts\python -m uvicorn sortified.main:app --reload --port 8000
        </pre>
      </div>
    </div>
  );
}
