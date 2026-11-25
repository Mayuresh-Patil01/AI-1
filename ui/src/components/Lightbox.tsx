import { useEffect } from "react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { api, type ImageItem } from "../api";

type Props = { images: ImageItem[]; index: number; onClose: () => void; onIndex: (i: number) => void };

const formatSize = (bytes: number) =>
  bytes > 1e6 ? `${(bytes / 1e6).toFixed(1)} MB` : `${Math.round(bytes / 1e3)} KB`;

export default function Lightbox({ images, index, onClose, onIndex }: Props) {
  const img = images[index];
  const prev = () => onIndex((index - 1 + images.length) % images.length);
  const next = () => onIndex((index + 1) % images.length);

  // Keyboard: ← → to browse, Esc to close
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowLeft") prev();
      if (e.key === "ArrowRight") next();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (!img) return null;

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ink-950/95 backdrop-blur-sm" onClick={onClose}>
      <div className="flex items-center justify-between px-6 py-4" onClick={(e) => e.stopPropagation()}>
        <div className="min-w-0">
          <p className="truncate font-medium">{img.name}</p>
          <p className="text-xs text-ink-400">
            {img.width && img.height ? `${img.width} × ${img.height} · ` : ""}
            {formatSize(img.size)}
            {img.taken_at ? ` · ${new Date(img.taken_at).toLocaleString()}` : ""}
          </p>
        </div>
        <button onClick={onClose} className="rounded-full p-2 text-ink-300 hover:bg-ink-800 hover:text-white">
          <X className="size-5" />
        </button>
      </div>

      <div className="relative flex flex-1 items-center justify-center px-16 pb-8">
        <img
          key={img.id}
          src={api.thumbnailUrl(img.id, "large")}
          alt={img.name}
          onClick={(e) => e.stopPropagation()}
          className="max-h-full max-w-full rounded-lg object-contain shadow-2xl animate-fade-up"
        />
        {images.length > 1 && (
          <>
            <NavButton side="left" onClick={prev}>
              <ChevronLeft className="size-6" />
            </NavButton>
            <NavButton side="right" onClick={next}>
              <ChevronRight className="size-6" />
            </NavButton>
          </>
        )}
      </div>
    </div>
  );
}

function NavButton({ side, onClick, children }: { side: "left" | "right"; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={`absolute ${side === "left" ? "left-4" : "right-4"} rounded-full bg-ink-800/80 p-3 text-ink-300 hover:bg-ink-700 hover:text-white`}
    >
      {children}
    </button>
  );
}
