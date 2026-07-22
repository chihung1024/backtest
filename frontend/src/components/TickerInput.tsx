import { LoaderCircle, Search, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { searchAssets } from "../api";
import type { ApiConnection, AssetSearchResult } from "../types";

export function TickerInput({
  value,
  connection,
  placeholder,
  searchLabel,
  clearLabel,
  onChange,
}: {
  value: string;
  connection: ApiConnection;
  placeholder: string;
  searchLabel: string;
  clearLabel: string;
  onChange: (value: string) => void;
}) {
  const [results, setResults] = useState<AssetSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeQuery, setActiveQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const timer = useRef<number | undefined>(undefined);
  const blurTimer = useRef<number | undefined>(undefined);
  const requestSequence = useRef(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listboxId = useId();

  useEffect(() => () => {
    window.clearTimeout(timer.current);
    window.clearTimeout(blurTimer.current);
  }, []);

  function update(next: string) {
    requestSequence.current += 1;
    onChange(next.toUpperCase());
    setResults([]);
    setOpen(false);
    setActiveIndex(-1);
    setLoading(false);
    window.clearTimeout(timer.current);
    window.clearTimeout(blurTimer.current);
    if (!next.trim()) return;
    timer.current = window.setTimeout(() => void search(next), 450);
  }

  async function search(query = value) {
    const clean = query.trim();
    if (!clean || !connection.baseUrl) return;
    window.clearTimeout(timer.current);
    const requestId = ++requestSequence.current;
    setLoading(true);
    setActiveQuery(clean);
    try {
      const found = await searchAssets(connection, clean);
      if (requestId !== requestSequence.current) return;
      setResults(found);
      setOpen(found.length > 0);
      setActiveIndex(found.length > 0 ? 0 : -1);
    } catch {
      if (requestId !== requestSequence.current) return;
      setResults([]);
      setOpen(false);
      setActiveIndex(-1);
    } finally {
      if (requestId === requestSequence.current) setLoading(false);
    }
  }

  function selectResult(result: AssetSearchResult) {
    requestSequence.current += 1;
    window.clearTimeout(timer.current);
    onChange(result.symbol);
    setOpen(false);
    setActiveIndex(-1);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      if (!results.length) return;
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) => current < 0 ? 0 : (current + 1) % results.length);
    } else if (event.key === "ArrowUp") {
      if (!results.length) return;
      event.preventDefault();
      setOpen(true);
      setActiveIndex((current) => current <= 0 ? results.length - 1 : current - 1);
    } else if (event.key === "Enter" && open && activeIndex >= 0) {
      event.preventDefault();
      selectResult(results[activeIndex]);
    } else if (event.key === "Escape" && open) {
      event.preventDefault();
      setOpen(false);
      setActiveIndex(-1);
    }
  }

  return (
    <div className="ticker-input">
      <input
        ref={inputRef}
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-activedescendant={open && activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined}
        aria-busy={loading}
        value={value}
        onChange={(event) => update(event.target.value)}
        onFocus={() => {
          window.clearTimeout(blurTimer.current);
          if (results.length) {
            setOpen(true);
            setActiveIndex((current) => current < 0 ? 0 : current);
          }
        }}
        onBlur={() => {
          blurTimer.current = window.setTimeout(() => {
            setOpen(false);
            setActiveIndex(-1);
          }, 150);
        }}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
      />
      {value && (
        <button
          type="button"
          className="ticker-input__clear"
          onClick={() => {
            update("");
            inputRef.current?.focus();
          }}
          aria-label={clearLabel}
        >
          <X size={14} />
        </button>
      )}
      <button
        type="button"
        className="ticker-input__search"
        onClick={() => {
          window.clearTimeout(blurTimer.current);
          inputRef.current?.focus();
          void search();
        }}
        aria-label={searchLabel}
      >
        {loading ? <LoaderCircle className="spin" size={17} /> : <Search size={17} />}
      </button>
      {open && (
        <div id={listboxId} className="ticker-results" role="listbox" aria-label={`${searchLabel}: ${activeQuery}`}>
          {results.map((result, index) => (
            <button
              id={`${listboxId}-option-${index}`}
              type="button"
              key={result.symbol}
              role="option"
              aria-selected={index === activeIndex}
              tabIndex={-1}
              className={index === activeIndex ? "active" : ""}
              onMouseMove={() => setActiveIndex(index)}
              onMouseDown={() => selectResult(result)}
            >
              <span className="ticker-results__symbol">{result.symbol}</span>
              <span className="ticker-results__name">{result.name}</span>
              <span className="ticker-results__meta">
                {[result.exchange, result.currency].filter(Boolean).join(" · ")}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
