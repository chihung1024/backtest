import { LoaderCircle, Search, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { searchAssets } from "../api";
import type { ApiConnection, AssetSearchResult } from "../types";

export function TickerInput({
  value,
  connection,
  placeholder,
  searchLabel,
  onChange,
}: {
  value: string;
  connection: ApiConnection;
  placeholder: string;
  searchLabel: string;
  onChange: (value: string) => void;
}) {
  const [results, setResults] = useState<AssetSearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeQuery, setActiveQuery] = useState("");
  const timer = useRef<number | undefined>(undefined);
  const requestSequence = useRef(0);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  function update(next: string) {
    requestSequence.current += 1;
    onChange(next.toUpperCase());
    setResults([]);
    setOpen(false);
    setLoading(false);
    window.clearTimeout(timer.current);
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
    } catch {
      if (requestId !== requestSequence.current) return;
      setResults([]);
      setOpen(false);
    } finally {
      if (requestId === requestSequence.current) setLoading(false);
    }
  }

  return (
    <div className="ticker-input">
      <input
        value={value}
        onChange={(event) => update(event.target.value)}
        onFocus={() => results.length && setOpen(true)}
        onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
      />
      {value && (
        <button type="button" className="ticker-input__clear" onClick={() => update("")} aria-label="Clear">
          <X size={14} />
        </button>
      )}
      <button
        type="button"
        className="ticker-input__search"
        onClick={() => void search()}
        aria-label={searchLabel}
      >
        {loading ? <LoaderCircle className="spin" size={17} /> : <Search size={17} />}
      </button>
      {open && (
        <div className="ticker-results" role="listbox" aria-label={`${activeQuery} results`}>
          {results.map((result) => (
            <button
              type="button"
              key={result.symbol}
              role="option"
              aria-selected={result.symbol === value}
              onMouseDown={() => {
                requestSequence.current += 1;
                window.clearTimeout(timer.current);
                onChange(result.symbol);
                setOpen(false);
              }}
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
