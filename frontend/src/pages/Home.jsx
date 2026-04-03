import { useEffect, useMemo, useState, useCallback, useRef } from "react"
import HeroBanner from "../components/HeroBanner"
import RecommendationRow from "../components/RecommendationRow"
import { useSearchFilter } from "../context/SearchFilterContext"
import api from "../api/axios"
import {
  getHybridRecommendations,
  getTrendingFallback,
  getMoviesByLanguage,
  getNowPlayingMovies,
  getUpcomingMovies
} from "../api/recommendations"

function Home() {
  const [profile, setProfile] = useState(null)
  const [hybridRecs, setHybridRecs] = useState([])
  const [trendingMovies, setTrendingMovies] = useState([])
  const [nowPlaying, setNowPlaying] = useState([])
  const [upcoming, setUpcoming] = useState([])
  const [becauseYouLiked, setBecauseYouLiked] = useState([])
  const [genreRecs, setGenreRecs] = useState([])
  const [languageMovies, setLanguageMovies] = useState([])

  const [loadingHybrid, setLoadingHybrid] = useState(true)
  const [loadingTrending, setLoadingTrending] = useState(true)
  const [loadingNowPlaying, setLoadingNowPlaying] = useState(true)
  const [loadingUpcoming, setLoadingUpcoming] = useState(true)
  const [loadingLanguage, setLoadingLanguage] = useState(false)

  // Use global search/filter metadata maps (for labels)
  const { languageMap } = useSearchFilter()
  
  const observerRef = useRef(null)

  /* ------------------ scroll animation ------------------ */
  const observeNodes = useCallback(() => {
    if (observerRef.current) observerRef.current.disconnect()
    
    observerRef.current = new IntersectionObserver( entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible")
          observerRef.current.unobserve(entry.target)
        }
      })
    }, { threshold: 0.1, rootMargin: "50px" })

    const nodes = document.querySelectorAll(".reveal-on-scroll:not(.visible)")
    nodes.forEach(node => observerRef.current.observe(node))
  }, [])

  useEffect(() => {
    observeNodes()
    return () => observerRef.current?.disconnect()
  }, [observeNodes, hybridRecs, trendingMovies, nowPlaying, upcoming, languageMovies])

  /* ------------------ profile fetch ------------------ */
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await api.get("/users/me")
        const user = response.data.user
        if (user && !user.id && user._id) { user.id = user._id }
        setProfile(user)
      } catch {
        try {
          const token = localStorage.getItem("cinescope-token")
          if (token) {
            const payload = JSON.parse(atob(token.split(".")[1]))
            setProfile({ id: payload.userId, name: "User" })
          } else { setProfile(null) }
        } catch { setProfile(null) }
      }
    }
    fetchProfile()
  }, [])

  /* ------------------ standard TMDB rows (Restored to curated highlight state) ------------------ */
  useEffect(() => {
    const fetchStandardRows = async () => {
      setLoadingTrending(true)
      setLoadingNowPlaying(true)
      setLoadingUpcoming(true)

      try {
        const movies = await getTrendingFallback()
        setTrendingMovies(movies.slice(0, 15).map(m => ({
          ...m, movie_id: m.id, explanation: { reason: "Trending this week", type: "trending" }
        })))
      } catch { setTrendingMovies([]) } finally { setLoadingTrending(false) }

      try {
        const data = await getNowPlayingMovies(1)
        setNowPlaying((data.results || []).slice(0, 15).map(m => ({
          ...m, movie_id: m.id, explanation: { reason: "In Theatres Now", type: "general" }
        })))
      } catch { setNowPlaying([]) } finally { setLoadingNowPlaying(false) }

      try {
        const data = await getUpcomingMovies(1)
        setUpcoming((data.results || []).slice(0, 15).map(m => ({
          ...m, movie_id: m.id, explanation: { reason: "Coming Soon", type: "general" }
        })))
      } catch { setUpcoming([]) } finally { setLoadingUpcoming(false) }
    }
    fetchStandardRows()
  }, [])

  /* ------------------ language preferences (Based on Profile ONLY) ------------------ */
  useEffect(() => {
    const preferredLang = profile?.preferredLanguage
    if (!preferredLang || preferredLang === "en") {
      setLanguageMovies([])
      return
    }
    const fetchLanguageMovies = async () => {
      setLoadingLanguage(true)
      try {
        const data = await getMoviesByLanguage(preferredLang, "popular")
        const langName = languageMap[preferredLang] || preferredLang.toUpperCase()
        setLanguageMovies((data.movies || []).slice(0, 20).map(m => ({
          ...m, movie_id: m.movie_id || m.id, explanation: { reason: `Popular in ${langName}`, type: "language_preference" }
        })))
      } catch { setLanguageMovies([]) } finally { setLoadingLanguage(false) }
    }
    fetchLanguageMovies()
  }, [profile?.preferredLanguage, languageMap])

  /* ------------------ hybrid recommendations (Personalized) ------------------ */
  useEffect(() => {
    if (!profile?.id) return
    const fetchRecommendations = async () => {
      setLoadingHybrid(true)
      try {
        const data = await getHybridRecommendations(profile.id, 40)
        const recs = data.recommendations || []
        setHybridRecs(recs.slice(0, 20))
        setBecauseYouLiked(recs.filter(r => r.explanation?.type === "content_similarity").slice(0, 15))
        setGenreRecs(recs.filter(r => r.explanation?.type === "genre_match").slice(0, 15))
      } catch {
        setHybridRecs([]); setBecauseYouLiked([]); setGenreRecs([])
      } finally { setLoadingHybrid(false) }
    }
    fetchRecommendations()
  }, [profile?.id])

  const nickname = (profile?.screenName || profile?.name || "Cinephile").replace(/^@/, "").replace(/\s+/g, "")
  const signatureLine = profile?.signatureLine?.trim() || "Start by rating a film you love and we'll shape your next perfect watch."

  return (
    <div>
      <section className="home-welcome reveal-on-scroll">
        <p className="home-welcome-kicker">Your CineScope Space</p>
        <h1>Hi {nickname}, start with your vibe.</h1>
        <p className="home-welcome-signature">"{signatureLine}"</p>
      </section>
      <div className="reveal-on-scroll"><HeroBanner /></div>

      {hybridRecs.length > 0 && (
        <div className="reveal-on-scroll">
          <RecommendationRow title="✨ Recommended For You" movies={hybridRecs} loading={loadingHybrid} showExplanation={true} />
        </div>
      )}

      {(nowPlaying.length > 0 || loadingNowPlaying) && (
        <div className="reveal-on-scroll">
          <RecommendationRow title="🎬 In Theatres Now" movies={nowPlaying} loading={loadingNowPlaying} showExplanation={false} />
        </div>
      )}

      {(languageMovies.length > 0 || loadingLanguage) && profile?.preferredLanguage && (
        <div className="reveal-on-scroll">
          <RecommendationRow title={`🌐 Popular in ${languageMap[profile.preferredLanguage] || profile.preferredLanguage.toUpperCase()}`} movies={languageMovies} loading={loadingLanguage} showExplanation={false} />
        </div>
      )}

      {(trendingMovies.length > 0 || loadingTrending) && (
        <div className="reveal-on-scroll">
          <RecommendationRow title="🔥 Trending This Week" movies={trendingMovies} loading={loadingTrending} showExplanation={false} />
        </div>
      )}

      {becauseYouLiked.length > 0 && (
        <div className="reveal-on-scroll">
          <RecommendationRow title="❤️ Because You Liked..." movies={becauseYouLiked} loading={false} showExplanation={true} />
        </div>
      )}

      {genreRecs.length > 0 && (
        <div className="reveal-on-scroll">
          <RecommendationRow title="🎭 Based on Your Favorite Genres" movies={genreRecs} loading={false} showExplanation={true} />
        </div>
      )}

      {(upcoming.length > 0 || loadingUpcoming) && (
        <div className="reveal-on-scroll">
          <RecommendationRow title="🍿 Coming Soon" movies={upcoming} loading={loadingUpcoming} showExplanation={false} />
        </div>
      )}
    </div>
  )
}

export default Home