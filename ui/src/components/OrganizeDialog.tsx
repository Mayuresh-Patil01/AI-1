import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, Sparkles, Tags, Wand2, X } from "lucide-react";
import { api, type Job } from "../api";
import Modal, { GhostButton, PrimaryButton } from "./Modal";

type Props = { hasAlbums: boolean; onClose: () => void; onFinished: () => void };

const SUGGESTIONS = ["Family", "Friends", "Food", "Travel", "Pets", "Screenshots", "Documents", "Nature", "Selfies", "Cars"];

export default function OrganizeDialog({ hasAlbums, onClose, onFinished }: Props) {
  const [mode, setMode] = useState<"auto" | "custom">("auto");
  const [autoCount, setAutoCount] = useState(true);
  const [count, setCount] = useState(8);
  const [categories, setCategories] = useState<string[]>([]);
  const [draft, setDraft] = useState("");
  const [strictness, setStrictness] = useState(0.4);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  const running = job?.state === "running";

  // If a job is already running (e.g. the dialog was closed and reopened), pick it up.
  useEffect(() => {
    api.currentJob().then((j) => j?.state === "running" && setJob(j));
  }, []);

  // Poll the job while it runs.
  useEffect(() => {
    if (!running) return;
    const t = setInterval(async () => {
      const j = await api.currentJob();
      if (!j) return;
      setJob(j);
      if (j.state === "done") onFinished();
    }, 800);
    return () => clearInterval(t);
  }, [running, onFinished]);

  function addCategory(name: string) {
    const parts = name.split(",").map((s) => s.trim()).filter(Boolean);
    setCategories((prev) => [...new Set([...prev, ...parts])]);
    setDraft("");
  }

  async function start() {
    setError(null);
    try {
      const j = await api.organize(
        mode === "auto"
          ? { mode, count: autoCount ? null : count }
          : { mode, categories: draft.trim() ? [...categories, draft.trim()] : categories, strictness },
      );
      setJob(j);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const canStart = mode === "auto" || categories.length + (draft.trim() ? 1 : 0) >= 2;

  return (
    <Modal title="Organize with AI" subtitle="SORTIFIED looks at every photo and sorts them into albums. Nothing on disk changes." onClose={onClose}>
      {job && job.state !== "error" ? (
        <JobProgress job={job} onClose={onClose} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3">
            <ModeCard active={mode === "auto"} onClick={() => setMode("auto")} icon={<Wand2 className="size-5" />} title="Auto-discover" text="AI finds natural groups and names them" />
            <ModeCard active={mode === "custom"} onClick={() => setMode("custom")} icon={<Tags className="size-5" />} title="My categories" text="You name the albums, AI fills them" />
          </div>

          {mode === "auto" ? (
            <div className="mt-6">
              <div className="flex items-center justify-between text-sm">
                <span className="text-ink-300">Number of albums</span>
                <label className="flex items-center gap-2 text-ink-400">
                  <input type="checkbox" checked={autoCount} onChange={(e) => setAutoCount(e.target.checked)} className="accent-brand-400" />
                  Let AI decide
                </label>
              </div>
              <div className={`mt-3 flex items-center gap-4 ${autoCount ? "opacity-40" : ""}`}>
                <input type="range" min={2} max={40} value={count} disabled={autoCount} onChange={(e) => setCount(+e.target.value)} className="flex-1 accent-brand-400" />
                <span className="w-8 text-right font-display text-lg">{count}</span>
              </div>
              <p className="mt-2 text-xs text-ink-400">Groups that end up with the same name are merged, so you may get fewer albums.</p>
            </div>
          ) : (
            <div className="mt-6">
              <div className="flex flex-wrap gap-2 rounded-lg border border-ink-600 bg-ink-800 p-2 focus-within:border-brand-400">
                {categories.map((c) => (
                  <span key={c} className="flex items-center gap-1 rounded-md bg-ink-700 py-1 pr-1 pl-2.5 text-sm">
                    {c}
                    <button onClick={() => setCategories(categories.filter((x) => x !== c))} className="rounded p-0.5 text-ink-400 hover:text-white">
                      <X className="size-3" />
                    </button>
                  </span>
                ))}
                <input
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if ((e.key === "Enter" || e.key === ",") && draft.trim()) {
                      e.preventDefault();
                      addCategory(draft);
                    }
                    if (e.key === "Backspace" && !draft && categories.length) setCategories(categories.slice(0, -1));
                  }}
                  placeholder={categories.length ? "Add another…" : "Type a category and press Enter"}
                  className="min-w-40 flex-1 bg-transparent px-1 py-1 text-sm placeholder:text-ink-400 focus:outline-none"
                />
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {SUGGESTIONS.filter((s) => !categories.includes(s)).map((s) => (
                  <button key={s} onClick={() => addCategory(s)} className="rounded-full px-2.5 py-1 text-xs text-ink-300 ring-1 ring-ink-700 hover:bg-ink-800 hover:text-white">
                    + {s}
                  </button>
                ))}
              </div>
              <div className="mt-6 text-sm text-ink-300">Strictness</div>
              <div className="mt-2 flex items-center gap-3 text-xs text-ink-400">
                <span>Relaxed</span>
                <input type="range" min={0} max={1} step={0.05} value={strictness} onChange={(e) => setStrictness(+e.target.value)} className="flex-1 accent-brand-400" />
                <span>Strict</span>
              </div>
              <p className="mt-2 text-xs text-ink-400">Photos that don't clearly match any category go to Unsorted.</p>
            </div>
          )}

          {hasAlbums && (
            <p className="mt-6 rounded-lg bg-amber-400/10 px-3 py-2 text-xs text-amber-300 ring-1 ring-amber-400/20">
              This replaces your current albums (including photos you moved by hand).
            </p>
          )}
          {(error || job?.error) && <p className="mt-4 text-sm text-red-400">{error ?? job?.error}</p>}

          <div className="mt-6 flex justify-end gap-2">
            <GhostButton onClick={onClose}>Cancel</GhostButton>
            <PrimaryButton onClick={start} disabled={!canStart}>
              <Sparkles className="size-4" /> Organize
            </PrimaryButton>
          </div>
        </>
      )}
    </Modal>
  );
}

function ModeCard(props: { active: boolean; onClick: () => void; icon: React.ReactNode; title: string; text: string }) {
  return (
    <button
      onClick={props.onClick}
      className={`rounded-xl p-4 text-left ring-1 transition ${
        props.active ? "bg-brand-500/10 ring-brand-400" : "bg-ink-800 ring-ink-700 hover:ring-ink-600"
      }`}
    >
      <div className={props.active ? "text-brand-400" : "text-ink-400"}>{props.icon}</div>
      <div className="mt-2 font-medium">{props.title}</div>
      <div className="mt-0.5 text-xs text-ink-400">{props.text}</div>
    </button>
  );
}

function JobProgress({ job, onClose }: { job: Job; onClose: () => void }) {
  const pct = job.total ? Math.round((job.done / job.total) * 100) : null;

  if (job.state === "done" && job.result) {
    const r = job.result;
    return (
      <div className="text-center">
        <CheckCircle2 className="mx-auto size-10 text-emerald-400" />
        <h3 className="mt-3 font-display text-lg font-semibold">
          {r.albums.length} album{r.albums.length === 1 ? "" : "s"} created
        </h3>
        <p className="mt-1 text-sm text-ink-400">
          {r.placed.toLocaleString()} photos sorted{r.unsorted ? ` · ${r.unsorted.toLocaleString()} left in Unsorted` : ""}
        </p>
        <div className="mt-4 flex flex-wrap justify-center gap-1.5">
          {r.albums.slice(0, 12).map((a) => (
            <span key={a.name} className="rounded-full bg-ink-800 px-2.5 py-1 text-xs ring-1 ring-ink-700">
              {a.name} <span className="text-ink-400">{a.count}</span>
            </span>
          ))}
        </div>
        <PrimaryButton onClick={onClose} className="mx-auto mt-6">
          View albums
        </PrimaryButton>
      </div>
    );
  }

  return (
    <div className="py-4">
      <div className="flex items-center gap-3 text-sm">
        <Loader2 className="size-4 animate-spin text-brand-400" />
        <span>{job.phase}</span>
        {pct !== null && <span className="ml-auto text-ink-400">{job.done.toLocaleString()} / {job.total.toLocaleString()}</span>}
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-ink-800">
        <div
          className={`h-full rounded-full brand-gradient transition-all duration-500 ${pct === null ? "w-1/3 animate-pulse" : ""}`}
          style={pct !== null ? { width: `${pct}%` } : undefined}
        />
      </div>
      <p className="mt-4 text-xs text-ink-400">You can close this window. The work continues in the background.</p>
    </div>
  );
}
