import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchStats } from "../api/stats";
import { fetchGrammarRules } from "../api/grammar";
import { fetchVocabulary } from "../api/vocabulary";
import type { Stats, GrammarRule, VocabItem } from "../api/types";

const statCards: { key: keyof Stats; label: string; to: string }[] = [
  { key: "grammar_rules", label: "Regeln", to: "/grammar" },
  { key: "vocabulary_items", label: "Vokabeln", to: "/vocabulary" },
  { key: "topics", label: "Themen", to: "/grammar" },
  { key: "assignments", label: "Aufgaben", to: "/assignments" },
];

export default function Home() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [rules, setRules] = useState<GrammarRule[]>([]);
  const [vocab, setVocab] = useState<VocabItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchStats(), fetchGrammarRules(), fetchVocabulary()])
      .then(([s, r, v]) => {
        setStats(s);
        setRules(r.slice(0, 5));
        setVocab(v.slice(0, 6));
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="py-16 text-center text-[13px] text-neutral-400">
        Laden…
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
          Übersicht
        </h1>
        <p className="text-[13px] text-neutral-400 mt-1">
          Dein Deutsch-Lernfortschritt auf einen Blick.
        </p>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {statCards.map(({ key, label, to }) => (
            <Link
              key={key}
              to={to}
              className="group border border-neutral-200 rounded-xl bg-white p-4 hover:border-neutral-300 transition-colors"
            >
              <p className="text-2xl font-semibold text-neutral-900 tracking-tight">
                {stats[key]}
              </p>
              <p className="text-[12px] text-neutral-400 mt-0.5 group-hover:text-neutral-500 transition-colors">
                {label}
              </p>
            </Link>
          ))}
        </div>
      )}

      {/* Recent grammar rules */}
      {rules.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[14px] font-medium text-neutral-900">
              Grammatikregeln
            </h2>
            <Link
              to="/grammar"
              className="text-[12px] text-neutral-400 hover:text-neutral-600 transition-colors"
            >
              Alle anzeigen
            </Link>
          </div>
          <div className="border border-neutral-200 rounded-xl bg-white divide-y divide-neutral-100 overflow-hidden">
            {rules.map((rule) => (
              <Link
                key={rule.id}
                to={`/grammar?topic=${encodeURIComponent(rule.topic)}`}
                className="flex items-start gap-3 px-4 py-3 hover:bg-neutral-50 transition-colors"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-neutral-900 truncate">
                    {rule.rule_name}
                  </p>
                  <p className="text-[12px] text-neutral-400 truncate mt-0.5">
                    {rule.topic}
                  </p>
                </div>
                <span className="shrink-0 text-[11px] text-neutral-300 bg-neutral-50 px-2 py-0.5 rounded-md">
                  {rule.examples.length} Bsp.
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}

      {/* Recent vocabulary */}
      {vocab.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[14px] font-medium text-neutral-900">
              Wortschatz
            </h2>
            <Link
              to="/vocabulary"
              className="text-[12px] text-neutral-400 hover:text-neutral-600 transition-colors"
            >
              Alle anzeigen
            </Link>
          </div>
          <div className="border border-neutral-200 rounded-xl bg-white divide-y divide-neutral-100 overflow-hidden">
            {vocab.map((item) => (
              <div key={item.id} className="flex items-center gap-3 px-4 py-3">
                <p className="text-[13px] font-medium text-neutral-900 min-w-0">
                  {item.article ? `${item.article} ` : ""}
                  {item.word}
                </p>
                <span className="text-[11px] text-neutral-300 bg-neutral-50 px-2 py-0.5 rounded-md shrink-0">
                  {item.word_class}
                </span>
                <p className="text-[12px] text-neutral-400 truncate ml-auto">
                  {item.definition_en}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Empty state if nothing ingested yet */}
      {stats &&
        stats.grammar_rules === 0 &&
        stats.vocabulary_items === 0 && (
          <div className="text-center py-12">
            <p className="text-[14px] text-neutral-500">
              Noch keine Inhalte vorhanden.
            </p>
            <p className="text-[13px] text-neutral-400 mt-1">
              Sende Fotos deiner Lehrbuchseiten an den Telegram-Bot, um
              loszulegen.
            </p>
          </div>
        )}
    </div>
  );
}
