import { useNavigate } from "react-router-dom"
import { useState } from "react"
import { addMovieToWatchlist, addMovieToLiked, addMovieToDisliked } from "../api/recommendations"

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
  const year = movie.release_date ? movie.release_date.slice(0, 4) : null

  const handleClick = () => {
    if (movieId) navigate(`/movie/${movieId}`)
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      handleClick()
    }
  }

  const handleAddToWatchlist = async (e) => {
    e.stopPropagation()
    if (!movieId) return
    try {
      await addMovieToWatchlist(movieId, "watchlist")
      setWatchlistAdded(true)
      setDislikedAdded(false)
    } catch (err) {
      console.error("[MovieCard] Failed to add to watchlist:", err?.response?.data || err?.message)
    }
  }

  const handleLikeMovie = async (e) => {
    e.stopPropagation()
    if (!movieId) return
    try {
      await addMovieToLiked(movieId)
      setLikedAdded(true)
      setDislikedAdded(false)
    } catch (err) {
      console.error("[MovieCard] Failed to like movie:", err?.response?.data || err?.message)
    }
  }

  const handleDislikeMovie = async (e) => {
    e.stopPropagation()
    if (!movieId) return
    try {
      await addMovieToDisliked(movieId)
      setDislikedAdded(true)
      setLikedAdded(false)
      setWatchlistAdded(false)
    } catch (err) {
      console.error("[MovieCard] Failed to dislike movie:", err?.response?.data || err?.message)
    }
  }

  if (!movie.title) return null

  return (
    <article
      className="rec-card"
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="button"
      tabIndex={0}
      aria-label={`${movie.title}${year ? `, ${year}` : ""}`}
    >
      <div className="rec-card-poster-wrap">
        {posterUrl ? (
          <img
            src={posterUrl}
            alt={movie.title}
            className="rec-card-poster"
            loading="lazy"
          />
        ) : (
          <div className="rec-card-poster rec-card-poster--placeholder">
            <span>{movie.title?.charAt(0) || "?"}</span>
          </div>
        )}

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
        {year && <span className="rec-card-year">{year}</span>}
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
