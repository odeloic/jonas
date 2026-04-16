import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchFlashcardSet } from "../api/flashcards";
import type { FlashcardSetDetail, FlashcardItem } from "../api/types";
import EmptyState from "../components/EmptyState";

function FlashcardCard({ item }: { item: FlashcardItem }) {
  const [flipped, setFlipped] = useState(false);

  const wordDisplay = [item.article, item.word].filter(Boolean).join(" ");
  const plural = item.plural ? `(${item.plural})` : null;

  return (
    <button
      onClick={() => setFlipped((f) => !f)}
      className="w-full text-left border border-neutral-200 rounded-xl bg-white overflow-hidden hover:border-neutral-300 transition-colors"
    >
      <div className="px-5 py-4 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <span className="text-[15px] font-semibold text-neutral-900">
              {wordDisplay}
            </span>
            {plural && (
              <span className="text-[13px] text-neutral-400 ml-1.5">
                {plural}
              </span>
            )}
          </div>
          <span className="text-[11px] text-neutral-400 bg-neutral-50 px-2 py-0.5 rounded-md shrink-0">
            {item.word_class}
          </span>
        </div>

        {flipped && (
          <div className="space-y-2 pt-1 border-t border-neutral-100">
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
            {item.definition_en && (
              <div>
                <p className="text-[11px] text-neutral-400 uppercase tracking-wide">
                  Englisch
                </p>
                <p className="text-[13px] text-neutral-600 mt-0.5">
                  {item.definition_en}
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
          </div>
        )}

        <p className="text-[11px] text-neutral-300">
          {flipped ? "Tippen zum Schließen" : "Tippen zum Aufdecken"}
        </p>
      </div>
    </button>
  );
}

export default function FlashcardDetail() {
  const { id } = useParams<{ id: string }>();
  const [set, setSet] = useState<FlashcardSetDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    fetchFlashcardSet(Number(id))
      .catch(() => setError("Vokabelkarten konnten nicht geladen werden."))
      .then((data) => data && setSet(data))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="py-12 text-center text-[13px] text-neutral-400">
        Laden…
      </div>
    );
  }

  if (error || !set) {
    return (
      <EmptyState
        title="Nicht gefunden"
        description={error ?? "Diese Vokabelkarte existiert nicht."}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
          Vokabelkarten
        </h1>
        <p className="text-[13px] text-neutral-400 mt-1">
          {set.items.length}{" "}
          {set.items.length === 1 ? "Wort" : "Wörter"} · Tippen zum Aufdecken
        </p>
      </div>

      {set.items.length === 0 ? (
        <EmptyState
          title="Keine Vokabeln"
          description="Dieses Set enthält keine Vokabeln."
        />
      ) : (
        <div className="space-y-3">
          {set.items.map((item) => (
            <FlashcardCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
