import { api, type ImageItem } from "../api";

type Props = { images: ImageItem[]; onOpen: (index: number) => void };

export default function PhotoGrid({ images, onOpen }: Props) {
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(170px,1fr))] gap-3">
      {images.map((img, i) => (
        <button
          key={img.id}
          onClick={() => onOpen(i)}
          className="group relative aspect-square overflow-hidden rounded-xl bg-ink-800 ring-1 ring-ink-700/60 transition hover:ring-brand-400/70 animate-fade-up"
          style={{ animationDelay: `${Math.min(i, 30) * 15}ms` }}
        >
          <img
            src={api.thumbnailUrl(img.id)}
            alt={img.name}
            loading="lazy"
            className="size-full object-cover transition duration-500 group-hover:scale-105"
          />
          <div className="pointer-events-none absolute inset-x-0 bottom-0 translate-y-2 bg-gradient-to-t from-black/80 to-transparent p-2 pt-8 text-left opacity-0 transition group-hover:translate-y-0 group-hover:opacity-100">
            <p className="truncate text-xs font-medium text-white">{img.name}</p>
          </div>
        </button>
      ))}
    </div>
  );
}
