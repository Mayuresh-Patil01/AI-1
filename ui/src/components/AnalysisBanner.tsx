import { useCallback, useEffect, useState } from "react";
import { Loader2, ScanSearch } from "lucide-react";
import { api, type AnalysisStatus, type Job } from "../api";
import { PrimaryButton } from "./Modal";

/**
 * Shows "N photos haven't been analyzed yet [Analyze now]" when needed, and a progress bar while
 * analysis runs. Calls onDone when analysis finishes so the parent can reload its results.
 */
export default function AnalysisBanner({ onDone, what }: { onDone: () => void; what: string }) {
  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);
  const running = job?.state === "running";

  const refresh = useCallback(async () => {
    const [s, j] = await Promise.all([api.analysisStatus(), api.currentJob()]);
    setStatus(s);
    setJob(j?.state === "running" ? j : null);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    if (!running) return;
    const t = setInterval(async () => {
      const j = await api.currentJob();
      if (j?.state === "running") return setJob(j);
      setJob(null);
      if (j?.state === "error") setError(j.error);
      await refresh();
      onDone();
    }, 800);
    return () => clearInterval(t);
  }, [running, refresh, onDone]);

  async function start() {
    setError(null);
    try {
      setJob(await api.analyze());
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (running && job) {
    const pct = job.total ? Math.round((job.done / job.total) * 100) : null;
    return (
      <div className="mb-6 rounded-xl bg-ink-900 p-4 ring-1 ring-ink-700">
        <div className="flex items-center gap-3 text-sm">
          <Loader2 className="size-4 animate-spin text-brand-400" />
          <span>{job.phase}</span>
          {pct !== null && <span className="ml-auto text-ink-400">{job.done.toLocaleString()} / {job.total.toLocaleString()}</span>}
        </div>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-ink-800">
          <div
            className={`h-full rounded-full brand-gradient transition-all duration-500 ${pct === null ? "w-1/3 animate-pulse" : ""}`}
            style={pct !== null ? { width: `${pct}%` } : undefined}
          />
        </div>
      </div>
    );
  }

  if (!status || status.pending === 0) return error ? <p className="mb-6 text-sm text-red-400">{error}</p> : null;

  return (
    <div className="mb-6 flex items-center gap-4 rounded-xl bg-brand-500/10 p-4 ring-1 ring-brand-400/30">
      <ScanSearch className="size-5 shrink-0 text-brand-400" />
      <p className="flex-1 text-sm">
        <span className="font-medium">{status.pending.toLocaleString()} photos haven't been analyzed yet.</span>{" "}
        <span className="text-ink-300">Analyze them to include them in {what}.</span>
        {error && <span className="block text-red-400">{error}</span>}
      </p>
      <PrimaryButton onClick={start}>Analyze now</PrimaryButton>
    </div>
  );
}
