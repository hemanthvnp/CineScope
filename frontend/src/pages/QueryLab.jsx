import { useState, useEffect, useRef } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { streamQuery } from "../api/query"
import "./QueryLab.css"

const EXAMPLE_QUERIES = [
  "Show trending sci-fi movies",
  "Recommend dark thriller movies like Se7en",
  "Summarize Interstellar reviews",
  "Find movies similar to Fight Club streamable in India",
  "Something funny and feel-good for tonight",
  "Best Christopher Nolan movies",
]

const FOLLOW_UPS = [
  "Show me more",
  "Only on Netflix",
  "Something more recent",
  "Only highly rated ones",
]

const INTENT_COLORS = {
  discover:        "#4f8ef7",
  find_similar:    "#a855f7",
  recommend:       "#10b981",
  search:          "#f59e0b",
  filter_provider: "#ec4899",
  summarize:       "#06b6d4",
  mood_based:      "#f97316",
  lookup:          "#64748b",
}

function MovieGrid({ movies, providersPending }) {
  const navigate = useNavigate()
  return (
    <div className="ql-movie-grid">
      {movies.map(movie => (
        <div
          key={movie.movie_id}
          className="ql-movie-card"
          onClick={() => navigate(`/movie/${movie.movie_id}`)}
          role="button"
          tabIndex={0}
          onKeyDown={e => (e.key === "Enter" || e.key === " ") && navigate(`/movie/${movie.movie_id}`)}
        >
          <div className="ql-poster-wrap">
            {movie.poster_path ? (
              <img
                src={`https://image.tmdb.org/t/p/w300${movie.poster_path}`}
                alt={movie.title}
                className="ql-poster"
              />
            ) : (
              <div className="ql-poster-placeholder">{movie.title?.[0] ?? "?"}</div>
            )}
            {movie.similarity_score != null && (
              <div className="ql-score-bar">
                <div className="ql-score-fill" style={{ width: `${Math.round(movie.similarity_score * 100)}%` }} />
              </div>
            )}
            {movie.vote_average > 0 && (
              <div className="ql-rating-badge">⭐ {movie.vote_average.toFixed(1)}</div>
            )}
          </div>

          <div className="ql-movie-info">
            <p className="ql-movie-title">{movie.title}</p>
            {movie.year && <p className="ql-movie-year">{movie.year}</p>}
            {movie.genres?.length > 0 && (
              <p className="ql-movie-genres">{movie.genres.slice(0,2).join(", ")}</p>
            )}
            {movie.explanation && (
              <p className="ql-movie-reason">{movie.explanation}</p>
            )}
            {providersPending ? (
              <div className="ql-providers"><span className="ql-shimmer ql-shimmer-providers" /></div>
            ) : movie.providers?.length > 0 && (
              <div className="ql-providers">
                {movie.providers.slice(0,3).map(p => (
                  p.logo
                    ? <img key={p.name} src={p.logo} alt={p.name} title={`${p.name} (${p.type})`} className="ql-provider-logo" />
                    : <span key={p.name} className="ql-provider-name">{p.name}</span>
                ))}
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

function SkeletonGrid({ count }) {
  return (
    <div className="ql-movie-grid">
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className="ql-movie-card ql-skeleton-card">
          <div className="ql-shimmer ql-shimmer-poster" />
          <div className="ql-movie-info">
            <span className="ql-shimmer ql-shimmer-line" />
            <span className="ql-shimmer ql-shimmer-line short" />
          </div>
        </div>
      ))}
    </div>
  )
}

function Turn({ turn }) {
  const searching = turn.status === "thinking" || turn.status === "searching"
  return (
    <div className="ql-turn">
      <div className="ql-user-msg">{turn.q}</div>

      <div className="ql-results">
        {turn.status === "thinking" && (
          <div className="ql-status"><span className="ql-spinner" /> Understanding your question…</div>
        )}

        {/* Meta bar */}
        {turn.intent && (
          <div className="ql-meta-bar">
            <span
              className="ql-intent-badge"
              style={{ background: INTENT_COLORS[turn.intent] || "#64748b" }}
            >
              {turn.intent}
            </span>
            {turn.refines && <span className="ql-followup-badge">follow-up</span>}
            <span className="ql-meta-item">"{turn.interpretedAs}"</span>
            <div className="ql-meta-right">
              {searching && <span className="ql-meta-item"><span className="ql-spinner ql-spinner-sm" /> searching</span>}
              {turn.degraded && <span className="ql-degraded-badge" title="The LLM was unavailable; a rule-based parser answered">fallback</span>}
              {turn.meta?.cache_hit && <span className="ql-cache-badge">cache hit</span>}
              {turn.meta && <span className="ql-meta-item">{turn.meta.execution_ms} ms</span>}
              {turn.meta && <span className="ql-meta-item">{turn.results.length} results</span>}
            </div>
          </div>
        )}

        {/* Services pipeline */}
        {turn.meta?.services_invoked?.length > 0 && (
          <div className="ql-pipeline">
            <span className="ql-pipeline-label">Pipeline:</span>
            {turn.meta.services_invoked.map((s, i) => (
              <span key={s} className="ql-pipeline-step">
                {i > 0 && <span className="ql-pipeline-arrow">→</span>}
                {s}
              </span>
            ))}
          </div>
        )}

        {/* Synthesis */}
        {turn.synthesis ? (
          <div className="ql-synthesis">
            <span className="ql-synthesis-icon">✦</span>
            {turn.synthesis}
          </div>
        ) : searching && turn.wantsSynthesis && turn.results.length > 0 && (
          <div className="ql-synthesis ql-synthesis-pending">
            <span className="ql-synthesis-icon">✦</span>
            Writing a summary…
          </div>
        )}

        {/* Movie grid */}
        {turn.results.length > 0 ? (
          <MovieGrid movies={turn.results} providersPending={turn.providersPending} />
        ) : searching ? (
          <SkeletonGrid count={Math.min(turn.maxResults, 6)} />
        ) : turn.status === "done" && (
          <div className="ql-status">No movies matched. Try loosening a constraint.</div>
        )}

        {turn.status === "error" && <div className="ql-error">⚠ {turn.error}</div>}

        {/* Raw JSON toggle */}
        {turn.raw && (
          <details className="ql-raw">
            <summary>Raw JSON response</summary>
            <pre className="ql-json">{JSON.stringify(turn.raw, null, 2)}</pre>
          </details>
        )}
      </div>
    </div>
  )
}

export default function QueryLab() {
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState(() => searchParams.get("q") || "")
  const [locale, setLocale] = useState("US")
  const [maxResults, setMaxResults] = useState(8)
  const [includeProviders, setIncludeProviders] = useState(true)
  const [includeSynthesis, setIncludeSynthesis] = useState(true)

  const [turns, setTurns] = useState([])
  const [conversation, setConversation] = useState(null)   // sent back to ask a follow-up
  const [busy, setBusy] = useState(false)
  const abortRef = useRef(null)
  const endRef = useRef(null)

  // Auto-run if query came from the search bar (?q=...)
  useEffect(() => {
    const q = searchParams.get("q")
    if (q) run(q, { newConversation: true })
    return () => abortRef.current?.abort()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" })
  }, [turns.length])

  const run = async (q = query, { newConversation = false } = {}) => {
    const text = q.trim()
    if (!text) return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const previous = newConversation ? null : conversation
    const id = `${Date.now()}-${Math.random()}`
    const turn = {
      id, q: text, status: "thinking", results: [], maxResults,
      wantsSynthesis: includeSynthesis, providersPending: false,
    }
    const update = (patch) => setTurns(ts => ts.map(t => (t.id === id ? { ...t, ...patch } : t)))

    setTurns(ts => (newConversation ? [turn] : [...ts, turn]))
    if (newConversation) setConversation(null)
    setQuery("")
    setBusy(true)

    try {
      const final = await streamQuery({
        q: text, conversation: previous, locale, maxResults, includeProviders, includeSynthesis,
        signal: controller.signal,
        onEvent: (event, data) => {
          if (event === "intent") {
            update({
              status: "searching", intent: data.intent, interpretedAs: data.interpreted_as,
              refines: data.refines_previous, degraded: data.degraded,
            })
          } else if (event === "preview") {
            update({ results: data.results, providersPending: true })
          } else if (event === "results") {
            update({ results: data.results, providersPending: false })
          } else if (event === "synthesis") {
            update({ synthesis: data.synthesis })
          }
        },
      })
      update({
        status: "done", intent: final.intent, interpretedAs: final.interpreted_as,
        results: final.results, synthesis: final.synthesis, meta: final.meta, raw: final,
        degraded: final.meta?.degraded, refines: (final.conversation?.turn ?? 1) > 1,
        providersPending: false,
      })
      setConversation(final.conversation || null)
    } catch (err) {
      if (controller.signal.aborted) return
      update({ status: "error", error: err.message || "Query failed" })
    } finally {
      if (abortRef.current === controller) setBusy(false)
    }
  }

  const startOver = () => {
    abortRef.current?.abort()
    setTurns([])
    setConversation(null)
    setBusy(false)
  }

  const handleKey = (e) => {
    // Same rule as the Send button: a second query mid-stream would abort the running turn
    // and leave its spinner going forever
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (!busy) run() }
  }

  const lastTurn = turns[turns.length - 1]
  const canFollowUp = conversation && lastTurn?.status === "done" && !busy

  return (
    <div className="ql-shell">

      {/* ── Header ── */}
      <div className="ql-header">
        <div className="ql-title-row">
          <span className="ql-badge">AI</span>
          <h1 className="ql-title">Query Lab</h1>
          {turns.length > 0 && (
            <button className="ql-new-btn" onClick={startOver}>New search</button>
          )}
        </div>
        <p className="ql-subtitle">
          Ask in plain language, then refine it in follow-ups. The AI layer classifies intent, plans tool calls,
          runs them in parallel, and streams each stage back as soon as it is ready.
        </p>
      </div>

      {/* ── Conversation ── */}
      {turns.length > 0 && (
        <div className="ql-thread">
          {turns.map(t => <Turn key={t.id} turn={t} />)}
          {canFollowUp && (
            <div className="ql-followups">
              <span className="ql-followups-label">Refine:</span>
              {FOLLOW_UPS.map(f => (
                <button key={f} className="ql-chip" onClick={() => run(f)}>{f}</button>
              ))}
            </div>
          )}
          <div ref={endRef} />
        </div>
      )}

      {/* ── Input ── */}
      <div className="ql-input-card">
        <textarea
          className="ql-textarea"
          placeholder={conversation
            ? 'Ask a follow-up — "only on Netflix", "something newer", "in Hindi"… or a new question'
            : 'Try "Show trending sci-fi movies" or "Summarize Interstellar reviews"…'}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={handleKey}
          rows={2}
        />

        <div className="ql-controls">
          <div className="ql-options">
            <label className="ql-option">
              <span>Locale</span>
              <select value={locale} onChange={e => setLocale(e.target.value)} className="ql-select">
                {["US","IN","GB","DE","JP","KR","FR","AU"].map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </label>

            <label className="ql-option">
              <span>Results</span>
              <select value={maxResults} onChange={e => setMaxResults(Number(e.target.value))} className="ql-select">
                {[4, 6, 8, 10, 15, 20].map(n => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </label>

            <label className="ql-toggle">
              <input type="checkbox" checked={includeProviders} onChange={e => setIncludeProviders(e.target.checked)} />
              <span>Providers</span>
            </label>

            <label className="ql-toggle">
              <input type="checkbox" checked={includeSynthesis} onChange={e => setIncludeSynthesis(e.target.checked)} />
              <span>Synthesis</span>
            </label>
          </div>

          <button className="ql-run-btn" onClick={() => run()} disabled={busy || !query.trim()}>
            {busy ? <span className="ql-spinner" /> : conversation ? "Send" : "Run Query"}
          </button>
        </div>

        {/* Example chips */}
        {turns.length === 0 && (
          <div className="ql-examples">
            {EXAMPLE_QUERIES.map(q => (
              <button key={q} className="ql-chip" onClick={() => run(q, { newConversation: true })}>
                {q}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
