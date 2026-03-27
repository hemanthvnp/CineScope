import { useNavigate } from "react-router-dom"
import { useState } from "react"
import { addMovieToWatchlist, addMovieToLiked, addMovieToDisliked } from "../api/recommendations"

/**
 * MovieCard Component
 *
 * A rich movie card displaying poster, title, rating badge, and
 * recommendation explanation. Navigates to movie details on click.
 *
 * Props:
 *   movie - Movie object with title, poster_path, vote_average, movie_id/id
 *   explanation - Optional { reason, type } from the explainability engine
 *   score - Optional recommendation score (0-1)
 *   showExplanation - Whether to show the explanation badge (default: true)
 */
function MovieCard({ movie, explanation, score, showExplanation = true }) {
  const navigate = useNavigate()
  const [watchlistAdded, setWatchlistAdded] = useState(false)
  const [likedAdded, setLikedAdded] = useState(false)
  const [dislikedAdded, setDislikedAdded] = useState(false)

  const movieId = movie.movie_id || movie.id
  const posterUrl = movie.poster_path
    ? `https://image.tmdb.org/t/p/w300${movie.poster_path}`
    : null
  const rating = movie.vote_average ? movie.vote_average.toFixed(1) : "N/A"

  const handleClick = () => {
    if (movieId) navigate(`/movie/${movieId}`)
  }

  const handleAddToWatchlist = async (e) => {
    e.stopPropagation()
    if (!movieId) return

    console.log(`[MovieCard] Adding movie ${movieId} to watchlist...`)
    try {
      const response = await addMovieToWatchlist(movieId, "watchlist")
      console.log(`[MovieCard] Success:`, response)
      setWatchlistAdded(true)
      setDislikedAdded(false)
    } catch (err) {
      console.error("[MovieCard] Failed to add to watchlist:", err?.response?.data || err?.message || err)
    }
  }

  const handleLikeMovie = async (e) => {
    e.stopPropagation()
    if (!movieId) return

    console.log(`[MovieCard] Liking movie ${movieId}...`)
    try {
      const response = await addMovieToLiked(movieId)
      console.log(`[MovieCard] Success:`, response)
      setLikedAdded(true)
      setDislikedAdded(false)
    } catch (err) {
      console.error("[MovieCard] Failed to like movie:", err?.response?.data || err?.message || err)
    }
  }

  const handleDislikeMovie = async (e) => {
    e.stopPropagation()
    if (!movieId) return

    console.log(`[MovieCard] Disliking movie ${movieId}...`)
    try {
      const response = await addMovieToDisliked(movieId)
      console.log(`[MovieCard] Success:`, response)
      setDislikedAdded(true)
      setLikedAdded(false)
      setWatchlistAdded(false)
    } catch (err) {
      console.error("[MovieCard] Failed to dislike movie:", err?.response?.data || err?.message || err)
    }
  }

  if (!posterUrl) return null

  return (
    <article className="rec-card" onClick={handleClick} role="button" tabIndex={0}>
      <div className="rec-card-poster-wrap">
        <img
          src={posterUrl}
          alt={movie.title}
          className="rec-card-poster"
          loading="lazy"
        />
        <div className="rec-card-hover-actions">
          <button
            type="button"
            className={`rec-card-action-btn ${watchlistAdded ? "active" : ""}`}
            onClick={handleAddToWatchlist}
            title="Add to Watchlist"
          >
            {watchlistAdded ? "✓ Watchlist" : "+ Watchlist"}
          </button>
          <button
            type="button"
            className={`rec-card-action-btn rec-card-action-btn--like ${likedAdded ? "active" : ""}`}
            onClick={handleLikeMovie}
            title="Like movie"
          >
            {likedAdded ? "♥ Liked" : "♥ Like"}
          </button>
          <button
            type="button"
            className={`rec-card-action-btn rec-card-action-btn--dislike ${dislikedAdded ? "active" : ""}`}
            onClick={handleDislikeMovie}
            title="I don't like this"
          >
            {dislikedAdded ? "👎 Disliked" : "👎 Dislike"}
          </button>
        </div>
        <div className="rec-card-rating-badge">⭐ {rating}</div>
        {score > 0 && (
          <div className="rec-card-score-bar">
            <div
              className="rec-card-score-fill"
              style={{ width: `${Math.min(score * 100, 100)}%` }}
            />
          </div>
        )}
      </div>

      <div className="rec-card-info">
        <h3 className="rec-card-title">{movie.title}</h3>
        {showExplanation && explanation?.reason && (
          <p className={`rec-card-reason rec-card-reason--${explanation.type || "general"}`}>
            {explanation.reason}
          </p>
        )}
        {showExplanation && explanation?.boost && (
          <p className="rec-card-boost">✨ {explanation.boost}</p>
        )}
        {movie.genres && movie.genres.length > 0 && (
          <div className="rec-card-genres">
            {movie.genres.slice(0, 2).map((g, i) => (
              <span key={i} className="rec-card-genre-chip">{g}</span>
            ))}
          </div>
        )}
      </div>
    </article>
  )
}

export default MovieCard
