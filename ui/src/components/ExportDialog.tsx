import { useState } from "react";
import { CheckCircle2, FolderOutput, Loader2, Undo2 } from "lucide-react";
import { api, formatBytes, type ExportPreview, type ExportResult } from "../api";
import Modal, { GhostButton, PrimaryButton } from "./Modal";

export default function ExportDialog({ onClose }: { onClose: () => void }) {
  const [dest, setDest] = useState("");
  const [includeUnsorted, setIncludeUnsorted] = useState(false);
  const [preview, setPreview] = useState<ExportPreview | null>(null);
  const [result, setResult] = useState<ExportResult | null>(null);
  const [undone, setUndone] = useState<{ removed: number; kept: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run<T>(fn: () => Promise<T>, then: (v: T) => void) {
    setBusy(true);
    setError(null);
    try {
      then(await fn());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const resetPreview = () => setPreview(null);

  return (
    <Modal title="Export albums to folders" subtitle="Copies each album into its own folder. Your original photos stay exactly where they are." onClose={onClose} wide>
      {result ? (
        <div className="text-center">
          {undone ? (
            <>
              <Undo2 className="mx-auto size-10 text-ink-300" />
              <h3 className="mt-3 font-display text-lg font-semibold">Export undone</h3>
              <p className="mt-1 text-sm text-ink-400">
                Removed {undone.removed.toLocaleString()} copied files
                {undone.kept ? ` · kept ${undone.kept} that were changed since` : ""}.
              </p>
            </>
          ) : (
            <>
              <CheckCircle2 className="mx-auto size-10 text-emerald-400" />
              <h3 className="mt-3 font-display text-lg font-semibold">{result.copied.toLocaleString()} photos copied</h3>
              <p className="mt-1 break-all text-sm text-ink-400">{result.dest}</p>
              {result.failed.length > 0 && <p className="mt-2 text-sm text-amber-300">{result.failed.length} could not be copied.</p>}
            </>
          )}
          <div className="mt-6 flex justify-center gap-2">
            {!undone && (
              <GhostButton disabled={busy} onClick={() => run(() => api.exportUndo(result.id), setUndone)}>
                {busy ? <Loader2 className="size-4 animate-spin" /> : <Undo2 className="size-4" />} Undo export
              </GhostButton>
            )}
            <PrimaryButton onClick={onClose}>Done</PrimaryButton>
          </div>
        </div>
      ) : (
        <>
          <label className="block text-sm text-ink-300">Export to</label>
          <input
            value={dest}
            onChange={(e) => {
              setDest(e.target.value);
              resetPreview();
            }}
            placeholder="D:\Sorted Photos"
            className="mt-2 w-full rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-sm placeholder:text-ink-400 focus:border-brand-400 focus:outline-none"
          />
          <p className="mt-1.5 text-xs text-ink-400">A new or empty folder works best. It can't be inside one of your library folders.</p>
          <label className="mt-4 flex items-center gap-2 text-sm text-ink-300">
            <input
              type="checkbox"
              checked={includeUnsorted}
              onChange={(e) => {
                setIncludeUnsorted(e.target.checked);
                resetPreview();
              }}
              className="accent-brand-400"
            />
            Also copy Unsorted photos into an "Unsorted" folder
          </label>

          {preview && (
            <div className="mt-5 rounded-xl bg-ink-950/60 p-4 ring-1 ring-ink-700">
              <div className="flex items-baseline justify-between">
                <span className="font-medium">
                  {preview.total.toLocaleString()} photos → {preview.folders.length} folders
                </span>
                <span className="text-xs text-ink-400">{formatBytes(preview.bytes)} will be copied</span>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {preview.folders.map((f) => (
                  <span key={f.name} className="rounded-md bg-ink-800 px-2 py-1 text-xs">
                    📁 {f.name} <span className="text-ink-400">{f.count}</span>
                  </span>
                ))}
              </div>
              <div className="mt-3 space-y-1 font-mono text-[11px] text-ink-400">
                {preview.sample.map((s) => (
                  <div key={s.dst} className="truncate" title={`${s.src} → ${s.dst}`}>
                    {s.dst.slice(preview.dest.length)}
                  </div>
                ))}
                {preview.total > preview.sample.length && <div>… and {(preview.total - preview.sample.length).toLocaleString()} more</div>}
              </div>
            </div>
          )}

          {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

          <div className="mt-6 flex justify-end gap-2">
            <GhostButton onClick={onClose}>Cancel</GhostButton>
            {preview ? (
              <PrimaryButton disabled={busy || preview.total === 0} onClick={() => run(() => api.exportApply(dest, includeUnsorted), setResult)}>
                {busy ? <Loader2 className="size-4 animate-spin" /> : <FolderOutput className="size-4" />}
                Copy {preview.total.toLocaleString()} photos
              </PrimaryButton>
            ) : (
              <PrimaryButton disabled={busy || !dest.trim()} onClick={() => run(() => api.exportPreview(dest, includeUnsorted), setPreview)}>
                {busy && <Loader2 className="size-4 animate-spin" />} Preview
              </PrimaryButton>
            )}
          </div>
        </>
      )}
    </Modal>
  );
}
