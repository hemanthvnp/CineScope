import { useEffect, useMemo, useRef, useState } from "react"
import HeroBanner from "../components/HeroBanner"
import RecommendationRow from "../components/RecommendationRow"
import MovieRow from "../components/MovieRow"
import { useSearchFilter } from "../context/SearchFilterContext"
import api from "../api/axios"
import {
  getHybridRecommendations,
  getTrendingFallback,
  getMoviesByLanguage,
  getNowPlayingMovies,
  getUpcomingMovies
} from "../api/recommendations"

/* ============================================================
   CONSTANTS
   ============================================================ */

const LANGUAGE_LABELS = {
  en: "English", hi: "Hindi", ta: "Tamil", te: "Telugu",
  ml: "Malayalam", kn: "Kannada", ko: "Korean", ja: "Japanese",
  fr: "French", es: "Spanish", de: "German", it: "Italian",
  pt: "Portuguese", zh: "Chinese", ru: "Russian"
}

const MOOD_OPTIONS = [
  { emoji: "🔥", label: "Thrill me", genre: 28, color: "#ff3b30", glowColor: "rgba(255,59,48,0.22)" },
  { emoji: "😂", label: "Make me laugh", genre: 35, color: "#ffd60a", glowColor: "rgba(255,214,10,0.18)" },
  { emoji: "😢", label: "Give me feels", genre: 18, color: "#60a5fa", glowColor: "rgba(96,165,250,0.18)" },
  { emoji: "😱", label: "Scare me", genre: 27, color: "#a78bfa", glowColor: "rgba(167,139,250,0.18)" },
  { emoji: "🌍", label: "Explore worlds", genre: 12, color: "#34d399", glowColor: "rgba(52,211,153,0.18)" },
  { emoji: "🕵️", label: "Mind games", genre: 53, color: "#fb923c", glowColor: "rgba(251,146,60,0.18)" },
]

const TIME_LABELS = () => {
  const h = new Date().getHours()
  if (h >= 5 && h < 12) return { greeting: "Good morning", emoji: "🌅", vibe: "Start your day with something great" }
  if (h >= 12 && h < 17) return { greeting: "Good afternoon", emoji: "☀️", vibe: "Perfect time for a film break" }
  if (h >= 17 && h < 21) return { greeting: "Good evening", emoji: "🌆", vibe: "Wind down with a great watch tonight" }
  return { greeting: "Late night", emoji: "🌙", vibe: "The best films come out after dark" }
}

/* ============================================================
   SUB-COMPONENTS
   ============================================================ */

/** Animated counter that ticks up on mount */
function AnimatedCount({ to, suffix = "" }) {
  const [val, setVal] = useState(0)
  const rafRef = useRef(null)
  useEffect(() => {
    const duration = 1200
    const start = performance.now()
    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1)
      const ease = 1 - Math.pow(1 - progress, 3)
      setVal(Math.round(ease * to))
      if (progress < 1) rafRef.current = requestAnimationFrame(tick)
    }
    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [to])
  return <>{val.toLocaleString()}{suffix}</>
}

/** Mood selector pill */
function MoodPicker({ onSelect, selected }) {
  return (
    <div className="mood-picker-wrap reveal-on-scroll">
      <div className="mood-picker-label">
        <span className="mood-picker-kicker">What's your vibe?</span>
      </div>
      <div className="mood-picker-row">
        {MOOD_OPTIONS.map((mood) => (
          <button
            key={mood.genre}
            className={`mood-btn${selected === mood.genre ? " mood-btn--active" : ""}`}
            style={{
              "--mood-color": mood.color,
              "--mood-glow": mood.glowColor,
            }}
            onClick={() => onSelect(selected === mood.genre ? null : mood.genre)}
          >
            <span className="mood-btn-emoji">{mood.emoji}</span>
            <span className="mood-btn-label">{mood.label}</span>
          </button>
        ))}
      </div>

      <style>{`
        .mood-picker-wrap {
          margin: 0.8rem 1.5rem 0;
          padding: 1.1rem 1.4rem;
          border-radius: 16px;
          border: 1px solid rgba(255,255,255,0.08);
          background: linear-gradient(145deg, rgba(14,14,20,0.96), rgba(8,8,12,0.96));
          position: relative;
          overflow: hidden;
        }
        .mood-picker-wrap::after {
          content: '';
          position: absolute;
          bottom: 0; right: 0;
          width: 160px; height: 80px;
          background: radial-gradient(ellipse at 100% 100%, rgba(255,59,48,0.06), transparent 70%);
          pointer-events: none;
        }
        .mood-picker-label { margin-bottom: 0.85rem; }
        .mood-picker-kicker {
          font-size: 0.72rem;
          text-transform: uppercase;
          letter-spacing: 0.18em;
          color: rgba(148,163,184,0.7);
        }
        .mood-picker-row {
          display: flex;
          gap: 0.55rem;
          flex-wrap: wrap;
        }
        .mood-btn {
          display: flex;
          align-items: center;
          gap: 0.45rem;
          padding: 0.5rem 0.9rem;
          border-radius: 999px;
          border: 1px solid rgba(255,255,255,0.1);
          background: rgba(255,255,255,0.03);
          color: #c0c0d0;
          cursor: pointer;
          font-size: 0.82rem;
          font-family: inherit;
          font-weight: 600;
          transition: all 0.22s cubic-bezier(0.2, 0.65, 0.2, 1);
          letter-spacing: 0.01em;
        }
        .mood-btn:hover {
          border-color: var(--mood-color, rgba(255,59,48,0.5));
          background: var(--mood-glow, rgba(255,59,48,0.1));
          color: #f0f0f5;
          transform: translateY(-2px);
          box-shadow: 0 4px 18px var(--mood-glow, rgba(255,59,48,0.12));
        }
        .mood-btn--active {
          border-color: var(--mood-color, rgba(255,59,48,0.6)) !important;
          background: var(--mood-glow, rgba(255,59,48,0.15)) !important;
          color: #f8f8ff !important;
          box-shadow: 0 0 20px var(--mood-glow, rgba(255,59,48,0.15)) !important;
          transform: translateY(-2px);
        }
        .mood-btn-emoji { font-size: 1rem; line-height: 1; }
        .mood-btn-label { line-height: 1; }
      `}</style>
    </div>
  )
}

/** Quick stats strip */
function StatsStrip({ totalRated, totalWatchlisted, totalRecs }) {
  return (
    <div className="stats-strip reveal-on-scroll">
      <div className="stats-item">
        <span className="stats-num"><AnimatedCount to={totalRated} /></span>
        <span className="stats-label">Films Rated</span>
      </div>
      <div className="stats-divider" />
      <div className="stats-item">
        <span className="stats-num"><AnimatedCount to={totalWatchlisted} /></span>
        <span className="stats-label">Watchlisted</span>
      </div>
      <div className="stats-divider" />
      <div className="stats-item">
        <span className="stats-num"><AnimatedCount to={totalRecs} /></span>
        <span className="stats-label">Picks For You</span>
      </div>
      <style>{`
        .stats-strip {
          margin: 0.8rem 1.5rem 0;
          padding: 1rem 1.4rem;
          border-radius: 14px;
          border: 1px solid rgba(255,255,255,0.07);
          background: rgba(8,8,12,0.9);
          display: flex;
          align-items: center;
          gap: 1.5rem;
        }
        .stats-item {
          display: flex;
          flex-direction: column;
          gap: 0.18rem;
        }
        .stats-num {
          font-size: 1.35rem;
          font-weight: 700;
          color: #f0f0f5;
          line-height: 1;
          font-feature-settings: "tnum";
          font-variant-numeric: tabular-nums;
        }
        .stats-label {
          font-size: 0.68rem;
          text-transform: uppercase;
          letter-spacing: 0.12em;
          color: #555568;
        }
        .stats-divider {
          width: 1px;
          height: 32px;
          background: rgba(255,255,255,0.08);
          flex-shrink: 0;
        }
      `}</style>
    </div>
  )
}

/** Section divider with label */
function SectionDivider({ label, icon }) {
  return (
    <div className="section-divider">
      <span className="section-divider-icon">{icon}</span>
      <span className="section-divider-label">{label}</span>
      <div className="section-divider-line" />
      <style>{`
        .section-divider {
          display: flex;
          align-items: center;
          gap: 0.6rem;
          margin: 1.5rem 1.5rem 0;
          padding: 0 0.2rem;
        }
        .section-divider-icon { font-size: 1rem; }
        .section-divider-label {
          font-size: 0.68rem;
          text-transform: uppercase;
          letter-spacing: 0.18em;
          color: #555568;
          white-space: nowrap;
          font-weight: 700;
        }
        .section-divider-line {
          flex: 1;
          height: 1px;
          background: linear-gradient(90deg, rgba(255,255,255,0.1), transparent);
        }
      `}</style>
    </div>
  )
}

/** Horizontal scroll progress indicator */
function useScrollProgress(ref) {
  const [progress, setProgress] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const handler = () => {
      const max = el.scrollWidth - el.clientWidth
      setProgress(max > 0 ? el.scrollLeft / max : 0)
    }
    el.addEventListener("scroll", handler, { passive: true })
    return () => el.removeEventListener("scroll", handler)
  }, [ref])
  return progress
}

/* ============================================================
   MAIN HOME COMPONENT
   ============================================================ */

function Home() {
  const [profile, setProfile] = useState(null)
  const [hybridRecs, setHybridRecs] = useState([])
  const [trendingMovies, setTrendingMovies] = useState([])
  const [nowPlaying, setNowPlaying] = useState([])
  const [upcoming, setUpcoming] = useState([])
  const [becauseYouLiked, setBecauseYouLiked] = useState([])
  const [genreRecs, setGenreRecs] = useState([])
  const [languageMovies, setLanguageMovies] = useState([])

  const [searchResults, setSearchResults] = useState([])
  const [loadingSearch, setLoadingSearch] = useState(false)

  const [loadingHybrid, setLoadingHybrid] = useState(true)
  const [loadingTrending, setLoadingTrending] = useState(true)
  const [loadingNowPlaying, setLoadingNowPlaying] = useState(true)
  const [loadingUpcoming, setLoadingUpcoming] = useState(true)
  const [loadingLanguage, setLoadingLanguage] = useState(false)

  const [selectedMood, setSelectedMood] = useState(null)
  const [userStats, setUserStats] = useState({ rated: 0, watchlisted: 0 })

  // Use global search/filter state
  const { search, year, genre } = useSearchFilter()
  const { greeting, emoji, vibe } = TIME_LABELS()

  /* ------ scroll reveal ------ */
  useEffect(() => {
    const nodes = document.querySelectorAll(".reveal-on-scroll")
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible")
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.08 }
    )
    nodes.forEach((node) => observer.observe(node))
    return () => observer.disconnect()
  })

  /* ------ profile ------ */
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await api.get("/users/me")
        const user = response.data.user
        if (user && !user.id && user._id) user.id = user._id
        setProfile(user)

        // Fetch user stats if endpoints exist
        try {
          const [ratedRes, watchRes] = await Promise.allSettled([
            api.get(`/users/${user.id}/ratings/count`),
            api.get(`/users/${user.id}/watchlist/count`),
          ])
          setUserStats({
            rated: ratedRes.value?.data?.count ?? 0,
            watchlisted: watchRes.value?.data?.count ?? 0,
          })
        } catch {
          // Silently ignore — stats are decorative
        }
      } catch {
        try {
          const token = localStorage.getItem("cinescope-token")
          if (token) {
            const payload = JSON.parse(atob(token.split(".")[1]))
            setProfile({ id: payload.userId, name: "User" })
          } else {
            setProfile(null)
          }
        } catch {
          setProfile(null)
        }
      }
    }
    fetchProfile()
  }, [])

  /* ------ hybrid recs ------ */
  useEffect(() => {
    if (!profile?.id) return
    const fetchRecommendations = async () => {
      setLoadingHybrid(true)
      try {
        const data = await getHybridRecommendations(profile.id, 60)
        const recs = data.recommendations || []
        const contentRecs = recs.filter(r => r.explanation?.type === "content_similarity")
        setBecauseYouLiked(contentRecs.slice(0, 20))
        const matchRecs = recs.filter(r => r.explanation?.type !== "content_similarity")
        setHybridRecs(matchRecs.slice(0, 20))
        const genreBasedRecs = recs.filter(r => r.explanation?.type === "genre_match")
        setGenreRecs(genreBasedRecs.slice(0, 15))
      } catch (error) {
        console.error("Failed to fetch recommendations:", error)
        setHybridRecs([]); setBecauseYouLiked([]); setGenreRecs([])
      } finally {
        setLoadingHybrid(false)
      }
    }
    fetchRecommendations()
  }, [profile?.id])

  /* ------ standard rows ------ */
  useEffect(() => {
    const fetchStandardRows = async () => {
      try {
        const movies = await getTrendingFallback()
        const mapped = movies.slice(0, 12).map(m => ({
          ...m, movie_id: m.id, explanation: { reason: "Trending this week", type: "trending" }
        }))
        setTrendingMovies(mapped)
      } catch { setTrendingMovies([]) }
      finally { setLoadingTrending(false) }

      try {
        const data = await getNowPlayingMovies(1)
        const mapped = (data.results || []).slice(0, 12).map(m => ({
          ...m, movie_id: m.id, explanation: { reason: "In Theatres Now", type: "general" }
        }))
        setNowPlaying(mapped)
      } catch { setNowPlaying([]) }
      finally { setLoadingNowPlaying(false) }

      try {
        const data = await getUpcomingMovies(1)
        const mapped = (data.results || []).slice(0, 12).map(m => ({
          ...m, movie_id: m.id, explanation: { reason: "Coming Soon", type: "general" }
        }))
        setUpcoming(mapped)
      } catch { setUpcoming([]) }
      finally { setLoadingUpcoming(false) }
    }
    fetchStandardRows()
  }, [])

  /* ------ language movies ------ */
  useEffect(() => {
    const preferredLang = profile?.preferredLanguage
    if (!preferredLang || preferredLang === "en") { setLanguageMovies([]); return }
    const fetchLanguageMovies = async () => {
      setLoadingLanguage(true)
      try {
        const data = await getMoviesByLanguage(preferredLang, "popular")
        const langName = LANGUAGE_LABELS[preferredLang] || preferredLang.toUpperCase()
        const mapped = (data.movies || []).slice(0, 15).map(m => ({
          ...m,
          movie_id: m.movie_id || m.id,
          explanation: { reason: `Popular in ${langName}`, type: "language_preference" }
        }))
        setLanguageMovies(mapped)
      } catch { setLanguageMovies([]) }
      finally { setLoadingLanguage(false) }
    }
    fetchLanguageMovies()
  }, [profile?.preferredLanguage])

  /* ------ search ------ */
  useEffect(() => {
    const q = (search || "").trim()
    if (q.length < 2) { setSearchResults([]); setLoadingSearch(false); return }
    setLoadingSearch(true)
    const t = setTimeout(async () => {
      try {
        const response = await api.get("/movies/search", { params: { query: q, page: 1 } })
        const results = response?.data?.results || []
        const mapped = results
          .filter((m) => m?.id && m?.title)
          .slice(0, 30)
          .map((m) => ({
            ...m,
            movie_id: m.id,
            explanation: { reason: `Search match for "${q}"`, type: "general" }
          }))
        setSearchResults(mapped)
      } catch (err) {
        console.error("Search failed:", err?.response?.data || err?.message || err)
        setSearchResults([])
      } finally {
        setLoadingSearch(false)
      }
    }, 350)
    return () => clearTimeout(t)
  }, [search])

  /* ------ filter utility ------ */
  const applyFilters = (movies, options = {}) => {
    const { includeSearchText = true } = options
    return movies.filter((movie) => {
      if (includeSearchText && search && !movie.title?.toLowerCase().includes(search.toLowerCase())) return false
      if (year) {
        const movieYear = (movie.release_date || movie.year || "")?.split("-")[0]
        if (movieYear !== year) return false
      }
      if (genre && movie.genre_ids) {
        const genreMap = { Action: 28, Comedy: 35, Drama: 18, Thriller: 53 }
        if (!movie.genre_ids.includes(genreMap[genre])) return false
      }
      return true
    })
  }

  const filteredSearchResults = useMemo(
    () => applyFilters(searchResults, { includeSearchText: false }),
    [searchResults, search, year, genre]
  )

  /* ------ mood filter (client-side) ------ */
  const applyMoodFilter = (movies) => {
    if (!selectedMood) return movies
    return movies.filter(m => m.genre_ids?.includes(selectedMood))
  }

  /* ------ display names ------ */
  const displayName = (profile?.screenName || profile?.name || "Cinephile").trim()
  const nickname = displayName.replace(/^@/, "").replace(/\s+/g, "")
  const signatureLine = profile?.signatureLine?.trim() || vibe

  const totalRecs = hybridRecs.length + becauseYouLiked.length + genreRecs.length

  return (
    <div>
      {/* ── WELCOME STRIP ── */}
      <section className="home-welcome reveal-on-scroll">
        <p className="home-welcome-kicker">
          {emoji} {greeting}
        </p>
        <h1>
          Hey <em>{nickname}</em>, let's find your next obsession.
        </h1>
        <p className="home-welcome-signature">
          &ldquo;{signatureLine}&rdquo;
        </p>
      </section>

      {/* ── STATS STRIP (only if logged in) ── */}
      {profile && (
        <StatsStrip
          totalRated={userStats.rated}
          totalWatchlisted={userStats.watchlisted}
          totalRecs={totalRecs}
        />
      )}

      {/* ── MOOD PICKER ── */}
      <MoodPicker onSelect={setSelectedMood} selected={selectedMood} />

      {/* ── HERO BANNER ── */}
      <div className="reveal-on-scroll" style={{ marginTop: "1rem" }}>
        <HeroBanner />
      </div>

      {/* ── SEARCH RESULTS ── */}
      {search?.trim()?.length >= 2 && (
        <div className="reveal-on-scroll">
          <RecommendationRow
            title={`🔎 Search Results`}
            movies={filteredSearchResults}
            loading={loadingSearch}
            emptyMessage="No matching movies found."
            showExplanation={false}
          />
        </div>
      )}

      {/* ── PERSONALIZED SECTION ── */}
      <SectionDivider label="Curated For You" icon="✦" />

      {/* 🎯 Recommended For You */}
      <div className="reveal-on-scroll">
        <RecommendationRow
          title="🎯 Recommended For You"
          movies={applyMoodFilter(applyFilters(hybridRecs))}
          loading={loadingHybrid}
          emptyMessage="Complete your profile to get better matches!"
          showExplanation={true}
        />
      </div>

      {/* ❤️ Because You Liked... */}
      {becauseYouLiked.length > 0 && (
        <div className="reveal-on-scroll">
          <RecommendationRow
            title="❤️ Because You Liked..."
            movies={applyMoodFilter(applyFilters(becauseYouLiked))}
            loading={loadingHybrid}
            showExplanation={true}
          />
        </div>
      )}

      {/* 🎭 Genre Picks */}
      {genreRecs.length > 0 && (
        <div className="reveal-on-scroll">
          <RecommendationRow
            title="🎭 Based on Your Favorite Genres"
            movies={applyMoodFilter(applyFilters(genreRecs))}
            loading={false}
            showExplanation={true}
          />
        </div>
      )}

      {/* ── DISCOVER SECTION ── */}
      <SectionDivider label="Discover" icon="◈" />

      {/* 🎬 In Theatres Now */}
      <div className="reveal-on-scroll">
        <RecommendationRow
          title="🎬 In Theatres Now"
          movies={applyMoodFilter(applyFilters(nowPlaying))}
          loading={loadingNowPlaying}
          emptyMessage="Could not load now playing movies."
          showExplanation={false}
        />
      </div>

      {/* 🌐 Language Pick */}
      {(languageMovies.length > 0 || loadingLanguage) && profile?.preferredLanguage && (
        <div className="reveal-on-scroll">
          <RecommendationRow
            title={`🌐 Popular in ${LANGUAGE_LABELS[profile.preferredLanguage] || profile.preferredLanguage.toUpperCase()}`}
            movies={applyMoodFilter(applyFilters(languageMovies))}
            loading={loadingLanguage}
            emptyMessage="No movies found in your preferred language."
            showExplanation={false}
          />
        </div>
      )}

      {/* 🔥 Trending */}
      <div className="reveal-on-scroll">
        <RecommendationRow
          title="🔥 Trending This Week"
          movies={applyMoodFilter(applyFilters(trendingMovies))}
          loading={loadingTrending}
          emptyMessage="Could not load trending movies."
          showExplanation={false}
        />
      </div>

      {/* ── COMING SOON SECTION ── */}
      <SectionDivider label="On the Horizon" icon="◉" />

      {/* 🍿 Upcoming */}
      <div className="reveal-on-scroll">
        <RecommendationRow
          title="🍿 Coming Soon"
          movies={applyMoodFilter(applyFilters(upcoming))}
          loading={loadingUpcoming}
          emptyMessage="Could not load upcoming movies."
          showExplanation={false}
        />
      </div>

      {/* ── BOTTOM MOOD CTA ── */}
      {selectedMood && (
        <div className="reveal-on-scroll" style={{ margin: "1rem 1.5rem 0" }}>
          <div style={{
            padding: "0.9rem 1.2rem",
            borderRadius: "12px",
            border: "1px dashed rgba(255,59,48,0.35)",
            background: "rgba(255,59,48,0.04)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "1rem"
          }}>
            <p style={{ color: "#c0c0d0", fontSize: "0.88rem", margin: 0 }}>
              Showing movies filtered by your current mood.
            </p>
            <button
              onClick={() => setSelectedMood(null)}
              style={{
                padding: "0.4rem 0.9rem",
                borderRadius: "999px",
                border: "1px solid rgba(255,59,48,0.4)",
                background: "rgba(255,59,48,0.1)",
                color: "#fca5a5",
                fontSize: "0.78rem",
                fontWeight: 700,
                cursor: "pointer",
                fontFamily: "inherit",
                whiteSpace: "nowrap",
                flexShrink: 0,
                transition: "all 0.2s ease"
              }}
            >
              Clear Mood ✕
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default Home
