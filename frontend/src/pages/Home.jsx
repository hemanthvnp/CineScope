import { useEffect, useState } from "react"
import HeroBanner from "../components/HeroBanner"
import RecommendationRow from "../components/RecommendationRow"
import MovieRow from "../components/MovieRow"
import Navbar from "../components/Navbar"
import api from "../api/axios"
import {
  getHybridRecommendations,
  getTrendingFallback,
  getMoviesByLanguage,
  getNowPlayingMovies,
  getUpcomingMovies
} from "../api/recommendations"

const LANGUAGE_LABELS = {
  en: "English",
  hi: "Hindi",
  ta: "Tamil",
  te: "Telugu",
  ml: "Malayalam",
  kn: "Kannada",
  ko: "Korean",
  ja: "Japanese",
  fr: "French",
  es: "Spanish",
  de: "German",
  it: "Italian",
  pt: "Portuguese",
  zh: "Chinese",
  ru: "Russian"
}

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

  // 🔍 search & filter state (from commit 944311e)
  const [searchText, setSearchText] = useState("")
  const [filters, setFilters] = useState({ year: "", genre: "" })

  /* ------------------ scroll animation ------------------ */
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
      { threshold: 0.12 }
    )

    nodes.forEach((node) => observer.observe(node))
    return () => observer.disconnect()
  })

  /* ------------------ profile fetch ------------------ */
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await api.get("/users/me")
        const user = response.data.user
        if (user && !user.id && user._id) {
          user.id = user._id
        }
        setProfile(user)
      } catch {
        // Fallback token extraction
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

  /* ------------------ recommendation fetches ------------------ */
  // Fetch hybrid recommendations
  useEffect(() => {
    if (!profile?.id) return

    const fetchRecommendations = async () => {
      setLoadingHybrid(true)
      try {
        const data = await getHybridRecommendations(profile.id, 40)
        const recs = data.recommendations || []

        setHybridRecs(recs.slice(0, 15))

        const contentRecs = recs.filter(r => r.explanation?.type === "content_similarity")
        setBecauseYouLiked(contentRecs.slice(0, 10))

        const genreBasedRecs = recs.filter(r => r.explanation?.type === "genre_match")
        setGenreRecs(genreBasedRecs.slice(0, 10))
      } catch (error) {
        console.error("Failed to fetch recommendations:", error)
        setHybridRecs([])
        setBecauseYouLiked([])
        setGenreRecs([])
      } finally {
        setLoadingHybrid(false)
      }
    }

    fetchRecommendations()
  }, [profile?.id])

  // Fetch standard TMDB rows (Trending, Now Playing, Upcoming)
  useEffect(() => {
    const fetchStandardRows = async () => {
      // Trending
      try {
        const movies = await getTrendingFallback()
        const mapped = movies.slice(0, 12).map(m => ({
          ...m, movie_id: m.id, explanation: { reason: "Trending this week", type: "trending" }
        }))
        setTrendingMovies(mapped)
      } catch (error) {
         setTrendingMovies([])
      } finally {
        setLoadingTrending(false)
      }

      // Now Playing
      try {
        const data = await getNowPlayingMovies(1)
        const mapped = (data.results || []).slice(0, 12).map(m => ({
          ...m, movie_id: m.id, explanation: { reason: "In Theatres Now", type: "general" }
        }))
        setNowPlaying(mapped)
      } catch (error) {
        setNowPlaying([])
      } finally {
        setLoadingNowPlaying(false)
      }

      // Upcoming
      try {
        const data = await getUpcomingMovies(1)
        const mapped = (data.results || []).slice(0, 12).map(m => ({
          ...m, movie_id: m.id, explanation: { reason: "Coming Soon", type: "general" }
        }))
        setUpcoming(mapped)
      } catch (error) {
        setUpcoming([])
      } finally {
        setLoadingUpcoming(false)
      }
    }
    fetchStandardRows()
  }, [])

  // Fetch language preferences
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
        const langName = LANGUAGE_LABELS[preferredLang] || preferredLang.toUpperCase()
        const mapped = (data.movies || []).slice(0, 15).map(m => ({
          ...m,
          movie_id: m.movie_id || m.id,
          explanation: { reason: `Popular in ${langName}`, type: "language_preference" }
        }))
        setLanguageMovies(mapped)
      } catch (error) {
        setLanguageMovies([])
      } finally {
        setLoadingLanguage(false)
      }
    }

    fetchLanguageMovies()
  }, [profile?.preferredLanguage])

  /* ------------------ Navbar handlers ------------------ */
  const handleSearch = (text) => {
    setSearchText(text)
  }

  const handleFilter = ({ year, genre }) => {
    setFilters({ year, genre })
  }

  /* ------------------ data filtering utility ------------------ */
  const applyFilters = (movies) => {
    return movies.filter((movie) => {
      // search by title
      if (searchText && !movie.title?.toLowerCase().includes(searchText.toLowerCase())) {
        return false
      }

      // filter by year
      if (filters.year) {
        const movieYear = (movie.release_date || movie.year || "")?.split("-")[0]
        if (movieYear !== filters.year) return false
      }

      // filter by genre
      if (filters.genre && movie.genre_ids) {
        const genreMap = { Action: 28, Comedy: 35, Drama: 18, Thriller: 53 }
        if (!movie.genre_ids.includes(genreMap[filters.genre])) {
          return false
        }
      }
      return true
    })
  }

  /* ------------------ profile text ------------------ */
  const displayName = (profile?.screenName || profile?.name || "Cinephile").trim()
  const nickname = displayName.replace(/^@/, "").replace(/\s+/g, "")
  const signatureLine = profile?.signatureLine?.trim() || "Start by rating a film you love and we'll shape your next perfect watch."

  return (
    <div>
      {/* 🔝 Navbar with search + filters */}
      <Navbar onSearch={handleSearch} onFilter={handleFilter} />

      <section className="home-welcome reveal-on-scroll">
        <p className="home-welcome-kicker">Your CineScope Space</p>
        <h1>Hi {nickname}, start with your vibe.</h1>
        <p className="home-welcome-signature">"{signatureLine}"</p>
      </section>

      <div className="reveal-on-scroll"><HeroBanner /></div>

      {/* 🎯 Recommended For You */}
      <div className="reveal-on-scroll">
        <RecommendationRow
          title="🎯 Recommended For You"
          movies={applyFilters(hybridRecs)}
          loading={loadingHybrid}
          emptyMessage="Rate some movies to get personalized recommendations!"
          showExplanation={true}
        />
      </div>

      {/* 🎬 Now Playing - Pure TMDB */}
      <div className="reveal-on-scroll">
        <RecommendationRow
          title="🎬 In Theatres Now"
          movies={applyFilters(nowPlaying)}
          loading={loadingNowPlaying}
          emptyMessage="Could not load now playing movies."
          showExplanation={false}
        />
      </div>

      {/* 🌐 Popular in Your Language */}
      {(languageMovies.length > 0 || loadingLanguage) && profile?.preferredLanguage && (
        <div className="reveal-on-scroll">
          <RecommendationRow
            title={`🌐 Popular in ${LANGUAGE_LABELS[profile.preferredLanguage] || profile.preferredLanguage.toUpperCase()}`}
            movies={applyFilters(languageMovies)}
            loading={loadingLanguage}
            emptyMessage="No movies found in your preferred language."
            showExplanation={false}
          />
        </div>
      )}

      {/* 🔥 Trending Movies */}
      <div className="reveal-on-scroll">
        <RecommendationRow
          title="🔥 Trending This Week"
          movies={applyFilters(trendingMovies)}
          loading={loadingTrending}
          emptyMessage="Could not load trending movies."
          showExplanation={false}
        />
      </div>

      {/* ❤️ Because You Liked X */}
      {becauseYouLiked.length > 0 && (
        <div className="reveal-on-scroll">
          <RecommendationRow
            title="❤️ Because You Liked..."
            movies={applyFilters(becauseYouLiked)}
            loading={false}
            showExplanation={true}
          />
        </div>
      )}

      {/* 🎭 Based on Your Favorite Genres */}
      {genreRecs.length > 0 && (
        <div className="reveal-on-scroll">
          <RecommendationRow
            title="🎭 Based on Your Favorite Genres"
            movies={applyFilters(genreRecs)}
            loading={false}
            showExplanation={true}
          />
        </div>
      )}

      {/* 🍿 Upcoming - Pure TMDB */}
      <div className="reveal-on-scroll">
        <RecommendationRow
          title="🍿 Coming Soon"
          movies={applyFilters(upcoming)}
          loading={loadingUpcoming}
          emptyMessage="Could not load upcoming movies."
          showExplanation={false}
        />
      </div>
    </div>
  )
}

export default Home