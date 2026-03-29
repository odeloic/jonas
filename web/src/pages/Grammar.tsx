import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fetchGrammarRules, fetchTopics } from "../api/grammar";
import type { GrammarRule, TopicSummary } from "../api/types";
import SearchInput from "../components/SearchInput";
import Badge from "../components/Badge";
import EmptyState from "../components/EmptyState";

export default function Grammar() {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTopic = searchParams.get("topic") || "";
  const [search, setSearch] = useState("");
  const [topics, setTopics] = useState<TopicSummary[]>([]);
  const [rules, setRules] = useState<GrammarRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const load = useCallback(() => {
    setLoading(true);
    const params: { topic?: string; q?: string } = {};
    if (activeTopic) params.topic = activeTopic;
    if (search) params.q = search;
    Promise.all([fetchGrammarRules(params), fetchTopics()])
      .then(([r, t]) => {
        setRules(r);
        setTopics(t);
      })
      .finally(() => setLoading(false));
  }, [activeTopic, search]);

  useEffect(() => {
    const timeout = setTimeout(load, search ? 250 : 0);
    return () => clearTimeout(timeout);
  }, [load, search]);

  function selectTopic(topic: string) {
    setExpanded(new Set());
    if (topic === activeTopic) {
      searchParams.delete("topic");
    } else {
      searchParams.set("topic", topic);
    }
    setSearchParams(searchParams, { replace: true });
  }

  function toggleExpand(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  // Group rules by topic
  const grouped = rules.reduce<Record<string, GrammarRule[]>>((acc, rule) => {
    (acc[rule.topic] ??= []).push(rule);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-neutral-900">
          Grammatik
        </h1>
        <p className="text-[13px] text-neutral-400 mt-1">
          Alle gesammelten Grammatikregeln durchsuchen.
        </p>
      </div>

      {/* Search */}
      <SearchInput
        value={search}
        onChange={setSearch}
        placeholder="Regeln durchsuchen…"
      />

      {/* Topic filters */}
      {topics.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <Badge active={!activeTopic} onClick={() => selectTopic("")}>
            Alle
          </Badge>
          {topics.map((t) => (
            <Badge
              key={t.topic}
              active={activeTopic === t.topic}
              onClick={() => selectTopic(t.topic)}
            >
              {t.topic}
              <span className="ml-1 opacity-50">{t.count}</span>
            </Badge>
          ))}
        </div>
      )}

      {/* Results */}
      {loading ? (
        <div className="py-12 text-center text-[13px] text-neutral-400">
          Laden…
        </div>
      ) : rules.length === 0 ? (
        <EmptyState
          title="Keine Regeln gefunden"
          description={
            search
              ? "Versuche einen anderen Suchbegriff."
              : "Noch keine Grammatikregeln vorhanden."
          }
        />
      ) : (
        <div className="space-y-8">
          {Object.entries(grouped).map(([topic, topicRules]) => (
            <section key={topic}>
              <div className="flex items-center gap-2 mb-2">
                <h2 className="text-[13px] font-medium text-neutral-500 uppercase tracking-wide">
                  {topic}
                </h2>
                <span className="text-[11px] text-neutral-300">
                  {topicRules.length}
                </span>
              </div>

              <div className="border border-neutral-200 rounded-xl bg-white divide-y divide-neutral-100 overflow-hidden">
                {topicRules.map((rule) => {
                  const isOpen = expanded.has(rule.id);
                  return (
                    <div key={rule.id}>
                      <button
                        onClick={() => toggleExpand(rule.id)}
                        className="w-full text-left px-4 py-3 hover:bg-neutral-50 transition-colors flex items-start gap-3"
                      >
                        <svg
                          className={`shrink-0 mt-0.5 text-neutral-300 transition-transform ${isOpen ? "rotate-90" : ""}`}
                          width="12"
                          height="12"
                          viewBox="0 0 15 15"
                          fill="none"
                        >
                          <path
                            d="M6 11V4l4.5 3.5L6 11Z"
                            fill="currentColor"
                          />
                        </svg>
                        <div className="min-w-0 flex-1">
                          <p className="text-[13px] font-medium text-neutral-900">
                            {rule.rule_name}
                          </p>
                          {!isOpen && (
                            <p className="text-[12px] text-neutral-400 truncate mt-0.5">
                              {rule.explanation.slice(0, 120)}
                              {rule.explanation.length > 120 ? "…" : ""}
                            </p>
                          )}
                        </div>
                        {rule.examples.length > 0 && (
                          <span className="shrink-0 text-[11px] text-neutral-300 bg-neutral-50 px-2 py-0.5 rounded-md">
                            {rule.examples.length} Bsp.
                          </span>
                        )}
                      </button>

                      {isOpen && (
                        <div className="px-4 pb-4 pt-0 pl-9 space-y-3">
                          <p className="text-[13px] text-neutral-600 leading-relaxed whitespace-pre-line">
                            {rule.explanation}
                          </p>

                          {rule.pattern && (
                            <div className="bg-neutral-50 border border-neutral-100 rounded-lg px-3 py-2">
                              <p className="text-[11px] text-neutral-400 uppercase tracking-wide mb-1">
                                Muster
                              </p>
                              <p className="text-[13px] text-neutral-700 font-mono">
                                {rule.pattern}
                              </p>
                            </div>
                          )}

                          {rule.examples.length > 0 && (
                            <div>
                              <p className="text-[11px] text-neutral-400 uppercase tracking-wide mb-1.5">
                                Beispiele
                              </p>
                              <ul className="space-y-1">
                                {rule.examples.map((ex, i) => (
                                  <li
                                    key={i}
                                    className="text-[13px] text-neutral-600 pl-3 border-l-2 border-accent-soft"
                                  >
                                    {ex}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
