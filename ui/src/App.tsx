import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, ImageOff, Loader2 } from "lucide-react";
import { api, type Folder, type ImageItem } from "./api";
import Sidebar from "./components/Sidebar";
import PhotoGrid from "./components/PhotoGrid";
import Lightbox from "./components/Lightbox";

const PAGE = 200;

export default function App() {
  const [engineOk, setEngineOk] = useState<boolean | null>(null);
  const [folders, setFolders] = useState<Folder[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [images, setImages] = useState<ImageItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [lightbox, setLightbox] = useState<number | null>(null);
  const [toast, setToast] = useState<{ text: string; error?: boolean } | null>(null);

  const notify = (text: string, error = false) => {
    setToast({ text, error });
    setTimeout(() => setToast(null), 3500);
  };

  const loadFolders = useCallback(async () => setFolders(await api.folders()), []);

  const loadImages = useCallback(async (folderId: number | null) => {
    setLoading(true);
    try {
      const res = await api.images(folderId, 0, PAGE);
      setImages(res.items);
      setTotal(res.total);
    } finally {
      setLoading(false);
    }
  }, []);

  // On startup: check the engine is running, then load the library.
  useEffect(() => {
    api
      .health()
      .then(() => {
        setEngineOk(true);
        return loadFolders();
      })
      .catch(() => setEngineOk(false));
  }, [loadFolders]);

  useEffect(() => {
    if (engineOk) loadImages(selected);
  }, [engineOk, selected, loadImages]);

  async function loadMore() {
    const res = await api.images(selected, images.length, PAGE);
    setImages((prev) => [...prev, ...res.items]);
  }

  async function handleAdd(path: string) {
    try {
      const res = await api.addFolder(path);
      notify(`Found ${res.scan.added.toLocaleString()} new photos`);
      await loadFolders();
      setSelected(res.id);
    } catch (e) {
      notify((e as Error).message, true);
    }
  }

  async function handleRescan(id: number) {
    const r = await api.rescan(id);
    notify(`Rescan: +${r.added} new, ${r.updated} changed, ${r.removed} gone`);
    await loadFolders();
    await loadImages(selected);
  }

  async function handleRemove(id: number) {
    await api.removeFolder(id);
    notify("Folder removed from library (files untouched)");
    if (selected === id) setSelected(null);
    await loadFolders();
    await loadImages(selected === id ? null : selected);
  }

  const title = selected === null ? "All photos" : folders.find((f) => f.id === selected)?.path ?? "";

  if (engineOk === false) return <EngineOffline />;

  return (
    <div className="flex h-full">
      <Sidebar
        folders={folders}
        selected={selected}
        onSelect={setSelected}
        onAdd={handleAdd}
        onRescan={handleRescan}
        onRemove={handleRemove}
      />

      <main className="flex-1 overflow-y-auto">
        <header className="sticky top-0 z-10 border-b border-ink-700/60 bg-ink-950/80 px-8 py-5 backdrop-blur">
          <h2 className="truncate font-display text-2xl font-semibold" title={title}>
            {selected === null ? title : title.split(/[\\/]/).pop()}
          </h2>
          <p className="mt-0.5 text-sm text-ink-400">
            {total.toLocaleString()} photo{total === 1 ? "" : "s"}
            {selected !== null && <span className="ml-2 text-ink-600">{title}</span>}
          </p>
        </header>

        <div className="p-8">
          {loading || engineOk === null ? (
            <div className="flex justify-center py-24 text-ink-400">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : images.length === 0 ? (
            <EmptyState hasFolders={folders.length > 0} />
          ) : (
            <>
              <PhotoGrid images={images} onOpen={setLightbox} />
              {images.length < total && (
                <div className="mt-8 flex justify-center">
                  <button onClick={loadMore} className="rounded-lg bg-ink-800 px-5 py-2 text-sm hover:bg-ink-700">
                    Load more ({(total - images.length).toLocaleString()} left)
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>

      {lightbox !== null && (
        <Lightbox images={images} index={lightbox} onIndex={setLightbox} onClose={() => setLightbox(null)} />
      )}

      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 rounded-xl px-4 py-3 text-sm shadow-xl animate-fade-up ${
            toast.error ? "bg-red-500/90 text-white" : "bg-ink-700 text-ink-100 ring-1 ring-ink-600"
          }`}
        >
          {toast.text}
        </div>
      )}
    </div>
  );
}

function EmptyState({ hasFolders }: { hasFolders: boolean }) {
  return (
    <div className="flex flex-col items-center py-24 text-center">
      <div className="mb-5 rounded-2xl bg-ink-800 p-5 ring-1 ring-ink-700">
        <ImageOff className="size-8 text-brand-400" />
      </div>
      <h3 className="font-display text-xl font-semibold">{hasFolders ? "No photos here" : "Your library is empty"}</h3>
      <p className="mt-2 max-w-sm text-sm text-ink-400">
        {hasFolders
          ? "This folder has no supported images (JPG, PNG, WEBP, HEIC…)."
          : "Paste a folder path in the sidebar to start. SORTIFIED only reads your photos — it never changes them without asking."}
      </p>
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
