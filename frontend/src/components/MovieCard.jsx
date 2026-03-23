import { useNavigate } from "react-router-dom"

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

  const movieId = movie.movie_id || movie.id
  const posterUrl = movie.poster_path
    ? `https://image.tmdb.org/t/p/w300${movie.poster_path}`
    : null
  const rating = movie.vote_average ? movie.vote_average.toFixed(1) : "N/A"

  const handleClick = () => {
    if (movieId) navigate(`/movie/${movieId}`)
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
