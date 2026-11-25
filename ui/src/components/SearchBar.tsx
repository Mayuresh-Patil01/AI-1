import { useEffect, useState } from "react";
import { Search, X } from "lucide-react";

/** Search box in the header. Press Enter to search, Esc or ✕ to clear. "/" focuses it from anywhere. */
export default function SearchBar({ value, onSearch, onClear }: { value: string; onSearch: (q: string) => void; onClear: () => void }) {
  const [text, setText] = useState(value);
  useEffect(() => setText(value), [value]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement;
      if (e.key === "/" && !typing) {
        e.preventDefault();
        document.getElementById("photo-search")?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (text.trim()) onSearch(text.trim());
      }}
      className="group relative w-full max-w-sm"
    >
      <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-400" />
      <input
        id="photo-search"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") {
            setText("");
            onClear();
            (e.target as HTMLInputElement).blur();
          }
        }}
        placeholder='Search: "dog on a beach", "receipts"…'
        className="w-full rounded-xl border border-ink-700 bg-ink-900 py-2 pr-9 pl-9 text-sm placeholder:text-ink-400 focus:border-brand-400 focus:outline-none"
      />
      {text ? (
        <button
          type="button"
          onClick={() => {
            setText("");
            onClear();
          }}
          className="absolute top-1/2 right-2.5 -translate-y-1/2 rounded p-0.5 text-ink-400 hover:text-white"
        >
          <X className="size-3.5" />
        </button>
      ) : (
        <kbd className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 rounded border border-ink-600 px-1.5 text-[10px] text-ink-400">/</kbd>
      )}
    </form>
  );
}
