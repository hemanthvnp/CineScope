import { useParams } from "react-router-dom"
import { useEffect, useState } from "react"
import api from "../api/axios"
import StarRating from "../components/StarRating"
import { submitRating, getMovieRatings } from "../api/ratings"
import {
  addMovieToWatchlist,
  addMovieToLiked,
  addMovieToDisliked
} from "../api/recommendations"

function MovieDetails() {
  const { id } = useParams()
  const [movie, setMovie] = useState(null)
  const [userRating, setUserRating] = useState(0)
  const [communityAvg, setCommunityAvg] = useState(0)
  const [ratingCount, setRatingCount] = useState(0)
  const [ratingStatus, setRatingStatus] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [watchlistStatus, setWatchlistStatus] = useState(null)

  useEffect(() => {
    api.get(`/movies/${id}`)
      .then(r => setMovie(r.data))
      .catch(err => console.error("Failed to fetch movie details:", err))
  }, [id])

  useEffect(() => {
    getMovieRatings(parseInt(id, 10))
      .then(data => {
        setCommunityAvg(data.average || 0)
        setRatingCount(data.count || 0)
        if (data.userRating) setUserRating(data.userRating)
      })
      .catch(() => {})
  }, [id])

  const numericId = parseInt(id, 10)

  const handleRate = async (value) => {
    if (isSubmitting) return
    setIsSubmitting(true)
    setRatingStatus("")
    try {
      await submitRating(numericId, value)
      setUserRating(value)
      setRatingStatus("Rating saved!")
      const data = await getMovieRatings(numericId)
      setCommunityAvg(data.average || 0)
      setRatingCount(data.count || 0)
    } catch {
      setRatingStatus("Failed to save rating")
    } finally {
      setIsSubmitting(false)
      setTimeout(() => setRatingStatus(""), 3000)
    }
  }

  const handleWatchlistAction = async (action) => {
    if (isSubmitting) return
    setIsSubmitting(true)
    setRatingStatus("")
    try {
      if (action === "watchlist") {
        await addMovieToWatchlist(numericId, "watchlist")
        setWatchlistStatus("watchlist")
        setRatingStatus("Added to watchlist!")
      } else if (action === "liked") {
        await addMovieToLiked(numericId)
        setWatchlistStatus("liked")
        setRatingStatus("Marked as liked!")
      } else if (action === "watched") {
        await addMovieToWatchlist(numericId, "watched")
        setWatchlistStatus("watched")
        setRatingStatus("Marked as watched!")
      } else if (action === "disliked") {
        await addMovieToDisliked(numericId)
        setWatchlistStatus("disliked")
        setRatingStatus("Got it — we'll show you fewer like this.")
      }
    } catch {
      setRatingStatus("Action failed. Please try again.")
    } finally {
      setIsSubmitting(false)
      setTimeout(() => setRatingStatus(""), 4000)
    }
  }

  if (!movie) return <div className="page-shell">Loading...</div>

  const genres = movie.genres?.map(g => g.name).join(", ")

  return (
    <section className="movie-details">
      <div className="movie-details-header">
        {movie.poster_path && (
          <img
            src={`https://image.tmdb.org/t/p/w400${movie.poster_path}`}
            alt={movie.title}
            className="movie-details-poster"
          />
        )}
        <div className="movie-details-body">
          <h1 className="gold-accent movie-details-title">{movie.title}</h1>
          {movie.tagline && <p className="movie-details-tagline">{movie.tagline}</p>}
          <p className="movie-details-overview">{movie.overview}</p>

          <div className="movie-meta">
            <p>⭐ TMDB Score: {movie.vote_average}</p>
            <p>📅 Release Date: {movie.release_date}</p>
            <p>⏱ Runtime: {movie.runtime} mins</p>
            {genres && <p>🎭 Genres: {genres}</p>}
          </div>

          {ratingCount > 0 && (
            <div className="movie-details-community">
              <p>
                👥 CineScope Community: <strong>{communityAvg}/10</strong>
                <span className="movie-details-count">
                  {" "}({ratingCount} {ratingCount === 1 ? "rating" : "ratings"})
                </span>
              </p>
            </div>
          )}

          <div className="movie-details-actions">
            <button
              className={`movie-action-btn ${watchlistStatus === "watchlist" ? "active" : ""}`}
              onClick={() => handleWatchlistAction("watchlist")}
              disabled={isSubmitting}
              title="Save to watchlist"
            >
              {watchlistStatus === "watchlist" ? "✓ In Watchlist" : "+ Watchlist"}
            </button>
            <button
              className={`movie-action-btn movie-action-btn--watched ${watchlistStatus === "watched" ? "active" : ""}`}
              onClick={() => handleWatchlistAction("watched")}
              disabled={isSubmitting}
              title="Mark as watched"
            >
              {watchlistStatus === "watched" ? "✓ Watched" : "👁 Watched"}
            </button>
            <button
              className={`movie-action-btn movie-action-btn--like ${watchlistStatus === "liked" ? "active" : ""}`}
              onClick={() => handleWatchlistAction("liked")}
              disabled={isSubmitting}
              title="Like this movie"
            >
              {watchlistStatus === "liked" ? "♥ Liked" : "♥ Like"}
            </button>
          </div>

          <div className="movie-details-rate">
            <div className="movie-details-rate-header">
              <h3>Your Rating</h3>
              <button
                className="dislike-btn-text"
                onClick={() => handleWatchlistAction("disliked")}
                disabled={isSubmitting}
                title="Not for me — show fewer like this"
              >
                👎 Not for me
              </button>
            </div>
            <StarRating
              currentRating={userRating}
              onRate={handleRate}
              disabled={isSubmitting}
              size={1.6}
            />
            {ratingStatus && (
              <p className="movie-details-rate-status">{ratingStatus}</p>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

export default MovieDetails
