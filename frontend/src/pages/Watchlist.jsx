import { useState, useEffect } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { getWatchlist, removeMovieFromWatchlist } from "../api/recommendations"
import "./Watchlist.css"

export default function Watchlist() {
  const [movies, setMovies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const location = useLocation()
  const navigate = useNavigate()

  const loadMovies = async () => {
    setLoading(true)
    setError("")
    try {
      const response = await getWatchlist(null, "watchlist")
      setMovies(response.watchlist || [])
    } catch (err) {
      setMovies([])
      setError(err?.response?.data?.error || err?.message || "Failed to load watchlist")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadMovies()
  }, [location])

  const deleteMovie = async (id) => {
    try {
      await removeMovieFromWatchlist(id)
    } catch (err) {
      setError(err?.response?.data?.error || err?.message || "Failed to remove movie")
    }
    setMovies(prev => prev.filter(m => (m.movie_id || m.id) !== id))
  }

  return (
    <div className="page-shell">
      <div className="watchlist-card">
        <div className="header">
          <div className="title-section">
            <h1>Watchlist</h1>
            <p>Save films you want to watch next in one curated shelf.</p>
          </div>
        </div>

        {loading && <div className="empty">Loading your watchlist...</div>}
        {!loading && error && <div className="empty">{error}</div>}
        {!loading && !error && movies.length === 0 && (
          <div className="empty">
            🎬 Your watchlist is empty
            <br />
            Add movies from the home page.
          </div>
        )}

        <div className="watchlist-movie-grid">
          {movies.map(movie => {
            const id = movie.movie_id || movie.id
            return (
              <div
                key={id}
                className="watchlist-movie-item"
                onClick={() => navigate(`/movie/${id}`)}
                role="button"
                tabIndex={0}
                onKeyDown={e => (e.key === "Enter" || e.key === " ") && navigate(`/movie/${id}`)}
                title="View movie details"
              >
                {movie.poster_path ? (
                  <img
                    src={`https://image.tmdb.org/t/p/w300${movie.poster_path}`}
                    alt={movie.title}
                    className="watchlist-poster"
                  />
                ) : (
                  <div className="watchlist-poster-placeholder">{movie.title?.charAt(0) || "?"}</div>
                )}
                <h3 className="watchlist-movie-title">{movie.title}</h3>
                {movie.release_date && (
                  <p className="watchlist-movie-year">{movie.release_date.slice(0, 4)}</p>
                )}
                {movie.vote_average > 0 && (
                  <p className="watchlist-movie-rating">⭐ {movie.vote_average.toFixed(1)}</p>
                )}
                <button
                  className="watchlist-delete-btn"
                  onClick={e => { e.stopPropagation(); deleteMovie(id) }}
                  title="Remove from Watchlist"
                >
                  ✕ Remove
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
