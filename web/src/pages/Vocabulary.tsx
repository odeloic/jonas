import { useCallback, useEffect, useState } from "react";
import { fetchVocabulary, fetchWordClasses } from "../api/vocabulary";
import type { VocabItem } from "../api/types";
import SearchInput from "../components/SearchInput";
import Badge from "../components/Badge";
import EmptyState from "../components/EmptyState";

export default function Vocabulary() {
  const [search, setSearch] = useState("");
  const [wordClasses, setWordClasses] = useState<string[]>([]);
  const [activeClass, setActiveClass] = useState("");
  const [items, setItems] = useState<VocabItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    const params: { q?: string; word_class?: string } = {};
    if (search) params.q = search;
    if (activeClass) params.word_class = activeClass;
    Promise.all([fetchVocabulary(params), fetchWordClasses()])
      .then(([v, wc]) => {
        setItems(v);
        setWordClasses(wc);
      })
      .finally(() => setLoading(false));
  }, [search, activeClass]);

  useEffect(() => {
    const timeout = setTimeout(load, search ? 250 : 0);
    return () => clearTimeout(timeout);
  }, [load, search]);

  function selectClass(wc: string) {
    setExpanded(null);
    setActiveClass(wc === activeClass ? "" : wc);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
          Wortschatz
        </h1>
        <p className="text-[13px] text-neutral-400 mt-1">
          {items.length > 0
            ? `${items.length} Vokabel${items.length !== 1 ? "n" : ""} gesammelt.`
            : "Alle gesammelten Vokabeln durchsuchen."}
        </p>
      </div>

      {/* Search */}
      <SearchInput
        value={search}
        onChange={setSearch}
        placeholder="Wort oder Übersetzung suchen…"
      />

      {/* Word class filters */}
      {wordClasses.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <Badge active={!activeClass} onClick={() => selectClass("")}>
            Alle
          </Badge>
          {wordClasses.map((wc) => (
            <Badge
              key={wc}
              active={activeClass === wc}
              onClick={() => selectClass(wc)}
            >
              {wc}
            </Badge>
          ))}
        </div>
      )}

      {/* Results */}
      {loading ? (
        <div className="py-12 text-center text-[13px] text-neutral-400">
          Laden…
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          title="Keine Vokabeln gefunden"
          description={
            search
              ? "Versuche einen anderen Suchbegriff."
              : "Noch keine Vokabeln vorhanden."
          }
        />
      ) : (
        <div className="border border-neutral-200 rounded-xl bg-white divide-y divide-neutral-100 overflow-hidden">
          {/* Table header */}
          <div className="grid grid-cols-[1fr_auto_1fr] gap-4 px-4 py-2 text-[11px] text-neutral-400 uppercase tracking-wide bg-neutral-50/50">
            <span>Wort</span>
            <span className="w-20 text-center">Klasse</span>
            <span className="text-right">Übersetzung</span>
          </div>

          {items.map((item) => {
            const isOpen = expanded === item.id;
            return (
              <div key={item.id}>
                <button
                  onClick={() => setExpanded(isOpen ? null : item.id)}
                  className="w-full text-left grid grid-cols-[1fr_auto_1fr] gap-4 px-4 py-3 hover:bg-neutral-50 transition-colors items-center"
                >
                  <div className="min-w-0">
                    <span className="text-[13px] font-medium text-neutral-900">
                      {item.article ? (
                        <span className="text-neutral-400 font-normal">
                          {item.article}{" "}
                        </span>
                      ) : null}
                      {item.word}
                    </span>
                    {item.plural && (
                      <span className="text-[12px] text-neutral-300 ml-1.5">
                        ({item.plural})
                      </span>
                    )}
                  </div>

                  <span className="w-20 text-center text-[11px] text-neutral-400 bg-neutral-50 px-2 py-0.5 rounded-md">
                    {item.word_class}
                  </span>

                  <p className="text-[13px] text-neutral-500 truncate text-right">
                    {item.definition_en || "—"}
                  </p>
                </button>

                {isOpen && (
                  <div className="px-4 pb-4 space-y-2 border-l-2 border-accent-soft ml-4">
                    {item.definition_de && (
                      <div>
                        <p className="text-[11px] text-neutral-400 uppercase tracking-wide">
                          Bedeutung
                        </p>
                        <p className="text-[13px] text-neutral-600 mt-0.5">
                          {item.definition_de}
                        </p>
                      </div>
                    )}
                    {item.example_sentence && (
                      <div>
                        <p className="text-[11px] text-neutral-400 uppercase tracking-wide">
                          Beispiel
                        </p>
                        <p className="text-[13px] text-neutral-600 mt-0.5 italic">
                          {item.example_sentence}
                        </p>
                      </div>
                    )}
                    {!item.definition_de && !item.example_sentence && (
                      <p className="text-[12px] text-neutral-300 italic">
                        Keine weiteren Details.
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
