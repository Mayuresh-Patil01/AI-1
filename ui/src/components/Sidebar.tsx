import { useState } from "react";
import { FolderPlus, Folder as FolderIcon, Images, Loader2, RefreshCw, Trash2, Sparkles } from "lucide-react";
import type { Folder } from "../api";

type Props = {
  folders: Folder[];
  selected: number | null;
  onSelect: (id: number | null) => void;
  onAdd: (path: string) => Promise<void>;
  onRescan: (id: number) => Promise<void>;
  onRemove: (id: number) => Promise<void>;
};

const shortName = (path: string) => path.split(/[\\/]/).filter(Boolean).pop() ?? path;

export default function Sidebar({ folders, selected, onSelect, onAdd, onRescan, onRemove }: Props) {
  const [path, setPath] = useState("");
  const [adding, setAdding] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const total = folders.reduce((n, f) => n + f.image_count, 0);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!path.trim()) return;
    setAdding(true);
    try {
      await onAdd(path);
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
      <div className="flex items-center gap-3 px-6 pt-6 pb-8">
        <img src="/favicon.svg" alt="" className="size-9 rounded-xl shadow-lg shadow-brand-500/20" />
        <div>
          <h1 className="font-display text-xl font-bold tracking-wide brand-text">SORTIFIED</h1>
          <p className="text-xs text-ink-400">AI photo organizer</p>
        </div>
      </div>

      <nav className="px-3">
        <button
          onClick={() => onSelect(null)}
          className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
            selected === null ? "bg-ink-700 text-white" : "text-ink-300 hover:bg-ink-800 hover:text-white"
          }`}
        >
          <Images className="size-4" />
          <span className="flex-1 text-left">All photos</span>
          <span className="text-xs text-ink-400">{total.toLocaleString()}</span>
        </button>
        <button
          disabled
          title="Coming in v1: AI albums"
          className="mt-1 flex w-full cursor-not-allowed items-center gap-3 rounded-lg px-3 py-2 text-sm text-ink-400"
        >
          <Sparkles className="size-4" />
          <span className="flex-1 text-left">AI albums</span>
          <span className="rounded-full bg-ink-700 px-2 py-0.5 text-[10px] uppercase tracking-wider">soon</span>
        </button>
      </nav>

      <div className="mt-8 px-6 text-[11px] font-semibold uppercase tracking-widest text-ink-400">Folders</div>
      <div className="mt-2 flex-1 space-y-0.5 overflow-y-auto px-3">
        {folders.length === 0 && (
          <p className="px-3 py-2 text-sm text-ink-400">No folders yet. Add one below.</p>
        )}
        {folders.map((f) => (
          <div
            key={f.id}
            className={`group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
              selected === f.id ? "bg-ink-700 text-white" : "text-ink-300 hover:bg-ink-800 hover:text-white"
            }`}
          >
            <button onClick={() => onSelect(f.id)} className="flex min-w-0 flex-1 items-center gap-3" title={f.path}>
              <FolderIcon className="size-4 shrink-0 text-brand-400" />
              <span className="truncate">{shortName(f.path)}</span>
            </button>
            {busyId === f.id ? (
              <Loader2 className="size-3.5 animate-spin text-ink-400" />
            ) : (
              <div className="hidden items-center gap-1 group-hover:flex">
                <button onClick={() => withBusy(f.id, onRescan)} title="Rescan" className="text-ink-400 hover:text-white">
                  <RefreshCw className="size-3.5" />
                </button>
                <button
                  onClick={() => withBusy(f.id, onRemove)}
                  title="Remove from library (files stay on disk)"
                  className="text-ink-400 hover:text-red-400"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
            )}
            <span className="text-xs text-ink-400 group-hover:hidden">{f.image_count.toLocaleString()}</span>
          </div>
        ))}
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
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-lg brand-gradient px-3 py-2 text-sm font-semibold text-ink-950 transition hover:opacity-90 disabled:opacity-40"
        >
          {adding ? <Loader2 className="size-4 animate-spin" /> : <FolderPlus className="size-4" />}
          {adding ? "Scanning…" : "Add folder"}
        </button>
      </form>
    </aside>
  );
}
