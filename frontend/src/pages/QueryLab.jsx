import { useState, useEffect } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { aiQuery } from "../api/query"
import "./QueryLab.css"

const EXAMPLE_QUERIES = [
  "Show trending sci-fi movies",
  "Recommend dark thriller movies like Se7en",
  "Summarize Interstellar reviews",
  "Find movies similar to Fight Club streamable in India",
  "Something funny and feel-good for tonight",
  "Best Christopher Nolan movies",
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

export default function QueryLab() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [query, setQuery] = useState(() => searchParams.get("q") || "")
  const [locale, setLocale] = useState("US")
  const [maxResults, setMaxResults] = useState(8)
  const [includeProviders, setIncludeProviders] = useState(true)
  const [includeSynthesis, setIncludeSynthesis] = useState(true)

  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState("")

  // Auto-run if query came from the search bar (?q=...)
  useEffect(() => {
    const q = searchParams.get("q")
    if (q) run(q)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const run = async (q = query) => {
    if (!q.trim()) return
    setLoading(true)
    setError("")
    setResult(null)
    try {
      const data = await aiQuery({ q: q.trim(), locale, maxResults, includeProviders, includeSynthesis })
      setResult(data)
    } catch (err) {
      setError(err?.response?.data?.error || err?.response?.data?.message || err.message || "Query failed")
    } finally {
      setLoading(false)
    }
  }

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); run() }
  }

  return (
    <div className="ql-shell">

      {/* ── Header ── */}
      <div className="ql-header">
        <div className="ql-title-row">
          <span className="ql-badge">AI</span>
          <h1 className="ql-title">Query Lab</h1>
        </div>
        <p className="ql-subtitle">
          One endpoint. Natural language. The AI layer classifies intent, plans tool calls,
          runs them in parallel, and aggregates results.
        </p>
      </div>

      {/* ── Input ── */}
      <div className="ql-input-card">
        <textarea
          className="ql-textarea"
          placeholder='Try "Show trending sci-fi movies" or "Summarize Interstellar reviews"…'
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

          <button className="ql-run-btn" onClick={() => run()} disabled={loading || !query.trim()}>
            {loading ? <span className="ql-spinner" /> : "Run Query"}
          </button>
        </div>

        {/* Example chips */}
        <div className="ql-examples">
          {EXAMPLE_QUERIES.map(q => (
            <button key={q} className="ql-chip" onClick={() => { setQuery(q); run(q) }}>
              {q}
            </button>
          ))}
        </div>
      </div>

      {/* ── Error ── */}
      {error && <div className="ql-error">⚠ {error}</div>}

      {/* ── Results ── */}
      {result && (
        <div className="ql-results">

          {/* Meta bar */}
          <div className="ql-meta-bar">
            <span
              className="ql-intent-badge"
              style={{ background: INTENT_COLORS[result.intent] || "#64748b" }}
            >
              {result.intent}
            </span>
            <span className="ql-meta-item">"{result.interpreted_as}"</span>
            <div className="ql-meta-right">
              {result.meta.cache_hit && <span className="ql-cache-badge">cache hit</span>}
              <span className="ql-meta-item">{result.meta.execution_ms} ms</span>
              <span className="ql-meta-item">{result.results.length} results</span>
            </div>
          </div>

          {/* Services pipeline */}
          <div className="ql-pipeline">
            <span className="ql-pipeline-label">Pipeline:</span>
            {result.meta.services_invoked.map((s, i) => (
              <span key={s} className="ql-pipeline-step">
                {i > 0 && <span className="ql-pipeline-arrow">→</span>}
                {s}
              </span>
            ))}
          </div>

          {/* Synthesis */}
          {result.synthesis && (
            <div className="ql-synthesis">
              <span className="ql-synthesis-icon">✦</span>
              {result.synthesis}
            </div>
          )}

          {/* Movie grid */}
          <div className="ql-movie-grid">
            {result.results.map(movie => (
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
                  {movie.providers?.length > 0 && (
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

          {/* Raw JSON toggle */}
          <details className="ql-raw">
            <summary>Raw JSON response</summary>
            <pre className="ql-json">{JSON.stringify(result, null, 2)}</pre>
          </details>
        </div>
      )}
    </div>
  )
}
