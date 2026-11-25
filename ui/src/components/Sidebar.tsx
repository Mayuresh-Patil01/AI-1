import { useState } from "react";
import {
  FolderPlus, Folder as FolderIcon, Images, Inbox, Loader2, Plus, RefreshCw, Sparkles, Trash2,
} from "lucide-react";
import { api, DRAG_TYPE, type Album, type Folder, type View } from "../api";

type Props = {
  folders: Folder[];
  albums: Album[];
  unsorted: number;
  view: View;
  onView: (v: View) => void;
  onAdd: (path: string) => Promise<void>;
  onRescan: (id: number) => Promise<void>;
  onRemove: (id: number) => Promise<void>;
  onOrganize: () => void;
  onNewAlbum: () => void;
  /** Photos were dropped on an album (albumId) or on Unsorted (null). */
  onDrop: (albumId: number | null, imageIds: number[]) => void;
};

const shortName = (path: string) => path.split(/[\\/]/).filter(Boolean).pop() ?? path;
const same = (a: View, b: View) => a.type === b.type && ("id" in a ? a.id : 0) === ("id" in b ? b.id : 0);

export default function Sidebar(props: Props) {
  const { folders, albums, unsorted, view, onView } = props;
  const [path, setPath] = useState("");
  const [adding, setAdding] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const total = folders.reduce((n, f) => n + f.image_count, 0);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!path.trim()) return;
    setAdding(true);
    try {
      await props.onAdd(path);
      setPath("");
    } finally {
      setAdding(false);
    }
  }

  async function withBusy(id: number, fn: (id: number) => Promise<void>) {
    setBusyId(id);
    try {
      await fn(id);
    } finally {
      setBusyId(null);
    }
  }

  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-ink-700/60 bg-ink-900/80 backdrop-blur">
      <div className="flex items-center gap-3 px-6 pt-6 pb-6">
        <img src="/favicon.svg" alt="" className="size-9 rounded-xl shadow-lg shadow-brand-500/20" />
        <div>
          <h1 className="font-display text-xl font-bold tracking-wide brand-text">SORTIFIED</h1>
          <p className="text-xs text-ink-400">AI photo organizer</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto pb-4">
        <nav className="px-3">
          <NavRow active={view.type === "all"} onClick={() => onView({ type: "all" })} icon={<Images className="size-4" />} label="All photos" count={total} />
        </nav>

        {/* ---------- Albums ---------- */}
        <SectionTitle
          action={
            albums.length > 0 && (
              <button onClick={props.onNewAlbum} title="New album" className="text-ink-400 hover:text-white">
                <Plus className="size-3.5" />
              </button>
            )
          }
        >
          Albums
        </SectionTitle>
        <div className="px-3">
          <button
            onClick={props.onOrganize}
            disabled={total === 0}
            className="mb-2 flex w-full items-center gap-2.5 rounded-lg bg-brand-500/10 px-3 py-2 text-sm font-medium text-brand-400 ring-1 ring-brand-400/30 transition hover:bg-brand-500/20 disabled:opacity-40"
          >
            <Sparkles className="size-4" />
            {albums.length ? "Re-organize with AI" : "Organize with AI"}
          </button>
          {albums.map((a) => (
            <DropTarget key={a.id} onDrop={(ids) => props.onDrop(a.id, ids)}>
              <NavRow
                active={same(view, { type: "album", id: a.id })}
                onClick={() => onView({ type: "album", id: a.id })}
                icon={
                  a.cover_id ? (
                    <img src={api.thumbnailUrl(a.cover_id)} alt="" className="size-6 rounded-md object-cover" />
                  ) : (
                    <div className="size-6 rounded-md bg-ink-700" />
                  )
                }
                label={a.name}
                count={a.count}
              />
            </DropTarget>
          ))}
          {albums.length > 0 && (
            <DropTarget onDrop={(ids) => props.onDrop(null, ids)}>
              <NavRow active={view.type === "unsorted"} onClick={() => onView({ type: "unsorted" })} icon={<Inbox className="size-4" />} label="Unsorted" count={unsorted} muted />
            </DropTarget>
          )}
        </div>

        {/* ---------- Folders ---------- */}
        <SectionTitle>Folders</SectionTitle>
        <div className="space-y-0.5 px-3">
          {folders.length === 0 && <p className="px-3 py-2 text-sm text-ink-400">No folders yet. Add one below.</p>}
          {folders.map((f) => (
            <div
              key={f.id}
              className={`group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                same(view, { type: "folder", id: f.id }) ? "bg-ink-700 text-white" : "text-ink-300 hover:bg-ink-800 hover:text-white"
              }`}
            >
              <button onClick={() => onView({ type: "folder", id: f.id })} className="flex min-w-0 flex-1 items-center gap-3" title={f.path}>
                <FolderIcon className="size-4 shrink-0 text-brand-400" />
                <span className="truncate">{shortName(f.path)}</span>
              </button>
              {busyId === f.id ? (
                <Loader2 className="size-3.5 animate-spin text-ink-400" />
              ) : (
                <div className="hidden items-center gap-1 group-hover:flex">
                  <button onClick={() => withBusy(f.id, props.onRescan)} title="Rescan" className="text-ink-400 hover:text-white">
                    <RefreshCw className="size-3.5" />
                  </button>
                  <button onClick={() => withBusy(f.id, props.onRemove)} title="Remove from library (files stay on disk)" className="text-ink-400 hover:text-red-400">
                    <Trash2 className="size-3.5" />
                  </button>
                </div>
              )}
              <span className="text-xs text-ink-400 group-hover:hidden">{f.image_count.toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>

      <form onSubmit={submit} className="border-t border-ink-700/60 p-4">
        <label className="mb-2 block text-xs text-ink-400">
          Paste a folder path <span className="text-ink-600">(Explorer → right-click → Copy as path)</span>
        </label>
        <input
          value={path}
          onChange={(e) => setPath(e.target.value)}
          placeholder="C:\Users\you\Pictures"
          className="w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm placeholder:text-ink-400 focus:border-brand-400 focus:outline-none"
        />
        <button
          type="submit"
          disabled={adding || !path.trim()}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg bg-ink-700 px-3 py-2 text-sm font-medium transition hover:bg-ink-600 disabled:opacity-40"
        >
          {adding ? <Loader2 className="size-4 animate-spin" /> : <FolderPlus className="size-4" />}
          {adding ? "Scanning…" : "Add folder"}
        </button>
      </form>
    </aside>
  );
}

function SectionTitle({ children, action }: { children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="mt-6 mb-2 flex items-center justify-between px-6 text-[11px] font-semibold uppercase tracking-widest text-ink-400">
      {children}
      {action}
    </div>
  );
}

function NavRow(props: { active: boolean; onClick: () => void; icon: React.ReactNode; label: string; count: number; muted?: boolean }) {
  return (
    <button
      onClick={props.onClick}
      className={`flex w-full items-center gap-3 rounded-lg px-3 py-1.5 text-sm transition ${
        props.active ? "bg-ink-700 text-white" : `${props.muted ? "text-ink-400" : "text-ink-300"} hover:bg-ink-800 hover:text-white`
      }`}
    >
      <span className="flex size-6 shrink-0 items-center justify-center">{props.icon}</span>
      <span className="flex-1 truncate text-left">{props.label}</span>
      <span className="text-xs text-ink-400">{props.count.toLocaleString()}</span>
    </button>
  );
}

/** Highlights while photos are dragged over it, and reports the dropped photo ids. */
function DropTarget({ children, onDrop }: { children: React.ReactNode; onDrop: (ids: number[]) => void }) {
  const [over, setOver] = useState(false);
  return (
    <div
      onDragOver={(e) => {
        if (!e.dataTransfer.types.includes(DRAG_TYPE)) return;
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        setOver(false);
        const raw = e.dataTransfer.getData(DRAG_TYPE);
        if (raw) onDrop(JSON.parse(raw));
      }}
      className={`rounded-lg transition ${over ? "bg-brand-500/20 ring-2 ring-brand-400" : ""}`}
    >
      {children}
    </div>
  );
}
