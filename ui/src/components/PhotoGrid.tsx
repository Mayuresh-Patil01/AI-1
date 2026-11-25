import { Check } from "lucide-react";
import { api, DRAG_TYPE, type ImageItem } from "../api";

type Props = {
  images: ImageItem[];
  selected: Set<number>;
  onToggle: (id: number, range: boolean) => void;
  onOpen: (index: number) => void;
};

export default function PhotoGrid({ images, selected, onToggle, onOpen }: Props) {
  const selecting = selected.size > 0;

  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(170px,1fr))] gap-3">
      {images.map((img, i) => {
        const isSelected = selected.has(img.id);
        return (
          <div
            key={img.id}
            draggable
            onDragStart={(e) => {
              // Dragging a selected photo drags the whole selection.
              const ids = isSelected ? [...selected] : [img.id];
              e.dataTransfer.setData(DRAG_TYPE, JSON.stringify(ids));
              e.dataTransfer.effectAllowed = "move";
              const badge = document.createElement("div");
              badge.textContent = `${ids.length} photo${ids.length > 1 ? "s" : ""}`;
              badge.style.cssText =
                "position:absolute;top:-100px;padding:6px 12px;border-radius:999px;background:#8b5cf6;color:#fff;font:600 13px Inter,sans-serif";
              document.body.appendChild(badge);
              e.dataTransfer.setDragImage(badge, 20, 16);
              setTimeout(() => badge.remove());
            }}
            onClick={(e) => {
              if (e.ctrlKey || e.metaKey || e.shiftKey || selecting) onToggle(img.id, e.shiftKey);
              else onOpen(i);
            }}
            className={`group relative aspect-square cursor-pointer overflow-hidden rounded-xl bg-ink-800 ring-1 transition animate-fade-up ${
              isSelected ? "ring-2 ring-brand-400" : "ring-ink-700/60 hover:ring-brand-400/70"
            }`}
            style={{ animationDelay: `${Math.min(i, 30) * 15}ms` }}
          >
            <img
              src={api.thumbnailUrl(img.id)}
              alt={img.name}
              loading="lazy"
              draggable={false}
              className={`size-full object-cover transition duration-500 ${isSelected ? "scale-90 rounded-lg" : "group-hover:scale-105"}`}
            />

            <button
              onClick={(e) => {
                e.stopPropagation();
                onToggle(img.id, e.shiftKey);
              }}
              title="Select"
              className={`absolute top-2 left-2 flex size-6 items-center justify-center rounded-full ring-2 transition ${
                isSelected
                  ? "bg-brand-400 text-ink-950 ring-brand-400"
                  : "bg-black/30 text-transparent ring-white/70 opacity-0 group-hover:opacity-100 hover:text-white/80"
              }`}
            >
              <Check className="size-3.5" strokeWidth={3} />
            </button>

            <div className="pointer-events-none absolute inset-x-0 bottom-0 translate-y-2 bg-gradient-to-t from-black/80 to-transparent p-2 pt-8 opacity-0 transition group-hover:translate-y-0 group-hover:opacity-100">
              <p className="truncate text-xs font-medium text-white">{img.name}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
