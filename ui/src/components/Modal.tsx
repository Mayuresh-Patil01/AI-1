import { useEffect } from "react";
import { X } from "lucide-react";

type Props = { title: string; subtitle?: string; onClose: () => void; children: React.ReactNode; wide?: boolean };

export default function Modal({ title, subtitle, onClose, children, wide }: Props) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-6 backdrop-blur-sm" onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        className={`w-full ${wide ? "max-w-2xl" : "max-w-lg"} max-h-full overflow-y-auto rounded-2xl bg-ink-900 shadow-2xl ring-1 ring-ink-700 animate-fade-up`}
      >
        <div className="flex items-start justify-between gap-4 border-b border-ink-700/60 px-6 py-5">
          <div>
            <h2 className="font-display text-lg font-semibold">{title}</h2>
            {subtitle && <p className="mt-1 text-sm text-ink-400">{subtitle}</p>}
          </div>
          <button onClick={onClose} className="rounded-full p-1.5 text-ink-400 hover:bg-ink-800 hover:text-white">
            <X className="size-4" />
          </button>
        </div>
        <div className="px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

export function PrimaryButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`flex items-center justify-center gap-2 rounded-lg brand-gradient px-4 py-2 text-sm font-semibold text-ink-950 transition hover:opacity-90 disabled:opacity-40 ${props.className ?? ""}`}
    />
  );
}

export function GhostButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`flex items-center justify-center gap-2 rounded-lg bg-ink-800 px-4 py-2 text-sm text-ink-100 ring-1 ring-ink-700 transition hover:bg-ink-700 disabled:opacity-40 ${props.className ?? ""}`}
    />
  );
}
