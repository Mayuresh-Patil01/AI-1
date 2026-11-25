import { useCallback, useEffect, useState } from "react";
import { Check, Copy, Loader2, MoonStar, PartyPopper, Trash2, Waves } from "lucide-react";
import { api, formatBytes, type CleanupImage, type DuplicateGroup, type ImageItem } from "../api";
import AnalysisBanner from "./AnalysisBanner";
import Lightbox from "./Lightbox";
import Modal, { GhostButton, PrimaryButton } from "./Modal";

type Tab = "duplicates" | "blurry" | "dark";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "duplicates", label: "Duplicates", icon: <Copy className="size-4" /> },
  { id: "blurry", label: "Blurry", icon: <Waves className="size-4" /> },
  { id: "dark", label: "Too dark", icon: <MoonStar className="size-4" /> },
];

/** Cleanup: review duplicates, blurry and dark photos, then keep them or send them to the Recycle Bin. */
export default function CleanupView({ onChanged, notify }: { onChanged: () => void; notify: (t: string, error?: boolean) => void }) {
  const [tab, setTab] = useState<Tab>("duplicates");
  const [version, setVersion] = useState(0); // bump to reload the current tab
  const reload = useCallback(() => setVersion((v) => v + 1), []);

  return (
    <div>
      <AnalysisBanner what="Cleanup" onDone={reload} />
      <div className="mb-6 flex gap-1 rounded-xl bg-ink-900 p-1 ring-1 ring-ink-700 w-fit">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 rounded-lg px-4 py-1.5 text-sm transition ${
              tab === t.id ? "bg-ink-700 text-white" : "text-ink-400 hover:text-white"
            }`}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>
      {tab === "duplicates" ? (
        <Duplicates key={version} onChanged={() => { reload(); onChanged(); }} notify={notify} />
      ) : (
        <QualityList key={`${tab}-${version}`} kind={tab} onChanged={() => { reload(); onChanged(); }} notify={notify} />
      )}
    </div>
  );
}

// ------------------------------------------------------------------ duplicates

function Duplicates({ onChanged, notify }: { onChanged: () => void; notify: (t: string, error?: boolean) => void }) {
  const [groups, setGroups] = useState<DuplicateGroup[] | null>(null);
  const [remove, setRemove] = useState<Set<number>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const [lightbox, setLightbox] = useState<{ images: ImageItem[]; index: number } | null>(null);

  useEffect(() => {
    api.duplicates().then((r) => {
      setGroups(r.groups);
      // Suggest removing every copy except the best one in each group.
      setRemove(new Set(r.groups.flatMap((g) => g.images.filter((i) => i.id !== g.keep_id).map((i) => i.id))));
    });
  }, []);

  if (!groups) return <Spinner />;
  if (!groups.length) return <AllClean text="No duplicates found." />;

  const toggle = (id: number) =>
    setRemove((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const sizeOf = (ids: Set<number>) =>
    groups.flatMap((g) => g.images).filter((i) => ids.has(i.id)).reduce((n, i) => n + i.size, 0);

  async function keepGroup(g: DuplicateGroup) {
    await api.keep(g.images.map((i) => i.id));
    notify("Kept all photos in this group");
    onChanged();
  }

  return (
    <>
      <SummaryBar
        text={`${groups.length} group${groups.length > 1 ? "s" : ""} of duplicates · ${formatBytes(sizeOf(remove))} can be freed`}
        count={remove.size}
        onTrash={() => setConfirming(true)}
      />
      <div className="space-y-4">
        {groups.map((g, gi) => (
          <div key={gi} className="rounded-2xl bg-ink-900 p-4 ring-1 ring-ink-700">
            <div className="mb-3 flex items-center gap-3 text-sm">
              <span className={`rounded-full px-2 py-0.5 text-xs ${g.kind === "exact" ? "bg-red-500/15 text-red-300" : "bg-amber-400/15 text-amber-300"}`}>
                {g.kind === "exact" ? "Identical files" : "Look the same"}
              </span>
              <span className="text-ink-400">{g.images.length} photos</span>
              <button onClick={() => keepGroup(g)} className="ml-auto text-xs text-ink-400 hover:text-white">
                Not duplicates, keep all
              </button>
            </div>
            <div className="flex flex-wrap gap-3">
              {g.images.map((img, i) => (
                <PhotoCard
                  key={img.id}
                  img={img}
                  marked={remove.has(img.id)}
                  badge={img.id === g.keep_id ? "Best" : undefined}
                  detail={`${img.width}×${img.height} · ${formatBytes(img.size)}`}
                  onToggle={() => toggle(img.id)}
                  onOpen={() => setLightbox({ images: g.images, index: i })}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
      {confirming && (
        <TrashDialog
          ids={[...remove]}
          bytes={sizeOf(remove)}
          onClose={() => setConfirming(false)}
          onDone={(msg) => {
            notify(msg);
            onChanged();
          }}
          notify={notify}
        />
      )}
      {lightbox && <Lightbox images={lightbox.images} index={lightbox.index} onIndex={(i) => setLightbox({ ...lightbox, index: i })} onClose={() => setLightbox(null)} />}
    </>
  );
}

// ------------------------------------------------------------------ blurry / dark

const SETTINGS = {
  blurry: { label: "Sharpness below", min: 10, max: 300, initial: 60, load: api.blurry, empty: "No blurry photos found." },
  dark: { label: "Brightness below", min: 5, max: 90, initial: 25, load: api.dark, empty: "No dark photos found." },
};

function QualityList({ kind, onChanged, notify }: { kind: "blurry" | "dark"; onChanged: () => void; notify: (t: string, error?: boolean) => void }) {
  const s = SETTINGS[kind];
  const [threshold, setThreshold] = useState(s.initial);
  const [items, setItems] = useState<CleanupImage[] | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const [lightbox, setLightbox] = useState<number | null>(null);

  useEffect(() => {
    const t = setTimeout(() => s.load(threshold).then((r) => setItems(r.items)), 200); // debounce the slider
    return () => clearTimeout(t);
  }, [threshold, s]);

  const toggle = (id: number) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  const bytes = (items ?? []).filter((i) => selected.has(i.id)).reduce((n, i) => n + i.size, 0);

  async function keepSelected() {
    await api.keep([...selected]);
    notify(`Kept ${selected.size} photos. They won't be suggested again`);
    onChanged();
  }

  return (
    <>
      <div className="mb-5 flex items-center gap-4 text-sm">
        <span className="text-ink-300">{s.label}</span>
        <input type="range" min={s.min} max={s.max} value={threshold} onChange={(e) => setThreshold(+e.target.value)} className="w-56 accent-brand-400" />
        <span className="w-10 text-ink-400">{threshold}</span>
        {items && items.length > 0 && (
          <button
            onClick={() => setSelected(selected.size === items.length ? new Set() : new Set(items.map((i) => i.id)))}
            className="ml-auto text-ink-400 hover:text-white"
          >
            {selected.size === items.length ? "Select none" : "Select all"}
          </button>
        )}
      </div>

      {!items ? (
        <Spinner />
      ) : !items.length ? (
        <AllClean text={s.empty} />
      ) : (
        <>
          <SummaryBar
            text={`${items.length} photo${items.length > 1 ? "s" : ""} · click photos to select them`}
            count={selected.size}
            onTrash={() => setConfirming(true)}
            extra={
              <GhostButton disabled={!selected.size} onClick={keepSelected}>
                <Check className="size-4" /> Keep
              </GhostButton>
            }
          />
          <div className="flex flex-wrap gap-3">
            {items.map((img, i) => (
              <PhotoCard
                key={img.id}
                img={img}
                marked={selected.has(img.id)}
                detail={kind === "blurry" ? `sharpness ${Math.round(img.sharpness ?? 0)}` : `brightness ${Math.round(img.brightness ?? 0)}`}
                onToggle={() => toggle(img.id)}
                onOpen={() => setLightbox(i)}
              />
            ))}
          </div>
        </>
      )}
      {confirming && (
        <TrashDialog ids={[...selected]} bytes={bytes} onClose={() => setConfirming(false)} onDone={(m) => { notify(m); onChanged(); }} notify={notify} />
      )}
      {lightbox !== null && items && <Lightbox images={items} index={lightbox} onIndex={setLightbox} onClose={() => setLightbox(null)} />}
    </>
  );
}

// ------------------------------------------------------------------ shared pieces

function PhotoCard(props: { img: CleanupImage; marked: boolean; badge?: string; detail: string; onToggle: () => void; onOpen: () => void }) {
  const { img, marked } = props;
  return (
    <div className="w-44">
      <div
        onClick={props.onToggle}
        className={`group relative aspect-square cursor-pointer overflow-hidden rounded-xl bg-ink-800 ring-2 transition ${
          marked ? "ring-red-400/80" : "ring-transparent hover:ring-ink-600"
        }`}
      >
        <img src={api.thumbnailUrl(img.id)} alt={img.name} loading="lazy" className={`size-full object-cover transition ${marked ? "opacity-50" : ""}`} />
        {props.badge && (
          <span className="absolute top-2 left-2 rounded-full bg-emerald-500 px-2 py-0.5 text-[10px] font-semibold text-ink-950">{props.badge}</span>
        )}
        {marked && (
          <span className="absolute top-2 right-2 flex size-6 items-center justify-center rounded-full bg-red-500 text-white">
            <Trash2 className="size-3.5" />
          </span>
        )}
        <button
          onClick={(e) => {
            e.stopPropagation();
            props.onOpen();
          }}
          className="absolute right-2 bottom-2 rounded-md bg-black/60 px-2 py-0.5 text-[11px] text-white opacity-0 transition group-hover:opacity-100"
        >
          View
        </button>
      </div>
      <p className="mt-1.5 truncate text-xs" title={img.path}>{img.name}</p>
      <p className="text-[11px] text-ink-400">{props.detail}</p>
    </div>
  );
}

function SummaryBar({ text, count, onTrash, extra }: { text: string; count: number; onTrash: () => void; extra?: React.ReactNode }) {
  return (
    <div className="sticky top-24 z-[5] mb-5 flex items-center gap-3 rounded-xl bg-ink-900/95 px-4 py-3 ring-1 ring-ink-700 backdrop-blur">
      <span className="flex-1 text-sm text-ink-300">{text}</span>
      {extra}
      <button
        disabled={!count}
        onClick={onTrash}
        className="flex items-center gap-2 rounded-lg bg-red-500/90 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-500 disabled:opacity-40"
      >
        <Trash2 className="size-4" /> Move {count} to Recycle Bin
      </button>
    </div>
  );
}

function TrashDialog(props: { ids: number[]; bytes: number; onClose: () => void; onDone: (msg: string) => void; notify: (t: string, error?: boolean) => void }) {
  const [busy, setBusy] = useState(false);
  async function go() {
    setBusy(true);
    try {
      const r = await api.trash(props.ids);
      props.onDone(`Moved ${r.trashed} photos to the Recycle Bin · freed ${formatBytes(r.freed)}` + (r.failed.length ? ` · ${r.failed.length} failed` : ""));
      props.onClose();
    } catch (e) {
      props.notify((e as Error).message, true);
      setBusy(false);
    }
  }
  return (
    <Modal title={`Move ${props.ids.length} photos to the Recycle Bin?`} onClose={props.onClose}>
      <p className="text-sm text-ink-300">
        This frees about <span className="font-semibold text-white">{formatBytes(props.bytes)}</span>. The photos are removed from
        SORTIFIED and moved to the Windows Recycle Bin, where you can restore them if you change your mind.
      </p>
      <div className="mt-6 flex justify-end gap-2">
        <GhostButton onClick={props.onClose}>Cancel</GhostButton>
        <PrimaryButton onClick={go} disabled={busy} className="!bg-none !bg-red-500 !text-white">
          {busy ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />} Move to Recycle Bin
        </PrimaryButton>
      </div>
    </Modal>
  );
}

function Spinner() {
  return (
    <div className="flex justify-center py-24 text-ink-400">
      <Loader2 className="size-6 animate-spin" />
    </div>
  );
}

function AllClean({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center py-20 text-center">
      <PartyPopper className="size-10 text-emerald-400" />
      <p className="mt-3 font-display text-lg font-semibold">All clean</p>
      <p className="mt-1 text-sm text-ink-400">{text}</p>
    </div>
  );
}
