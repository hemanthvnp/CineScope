import { useParams } from "react-router-dom"
import { useEffect, useState } from "react"
import api from "../api/axios"
import StarRating from "../components/StarRating"
import { submitRating, getMovieRatings } from "../api/ratings"

function MovieDetails() {
  const { id } = useParams()
  const [movie, setMovie] = useState(null)
  const [userRating, setUserRating] = useState(0)
  const [communityAvg, setCommunityAvg] = useState(0)
  const [ratingCount, setRatingCount] = useState(0)
  const [ratingStatus, setRatingStatus] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Fetch movie details from TMDB
  useEffect(() => {
    const fetchDetails = async () => {
      try {
        const response = await api.get(`/movies/${id}`)
        setMovie(response.data)
      } catch (error) {
        console.error("Failed to fetch movie details:", error)
      }
    }
    fetchDetails()
  }, [id])

  // Fetch existing rating data
  useEffect(() => {
    const fetchRatings = async () => {
      try {
        const data = await getMovieRatings(parseInt(id, 10))
        setCommunityAvg(data.average || 0)
        setRatingCount(data.count || 0)
        if (data.userRating) {
          setUserRating(data.userRating)
        }
      } catch {
        // Rating service may not be available — that's fine
      }
    }
    fetchRatings()
  }, [id])

  const handleRate = async (value) => {
    if (isSubmitting) return
    setIsSubmitting(true)
    setRatingStatus("")

    try {
      await submitRating(parseInt(id, 10), value)
      setUserRating(value)
      setRatingStatus("Rating saved!")

      // Refresh community stats
      const data = await getMovieRatings(parseInt(id, 10))
      setCommunityAvg(data.average || 0)
      setRatingCount(data.count || 0)
    } catch (error) {
      console.error("Failed to submit rating:", error)
      setRatingStatus("Failed to save rating")
    } finally {
      setIsSubmitting(false)
      setTimeout(() => setRatingStatus(""), 3000)
    }
  }

  if (!movie) return <div className="page-shell">Loading...</div>

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
            {movie.genres && (
              <p>🎭 Genres: {movie.genres.map(g => g.name).join(", ")}</p>
            )}
          </div>

          {/* Community rating */}
          {ratingCount > 0 && (
            <div className="movie-details-community">
              <p>
                👥 CineScope Community: <strong>{communityAvg}/10</strong>
                <span className="movie-details-count"> ({ratingCount} {ratingCount === 1 ? "rating" : "ratings"})</span>
              </p>
            </div>
          )}

          {/* User rating widget */}
          <div className="movie-details-rate">
            <h3>Your Rating</h3>
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