import { useParams } from "react-router-dom"
import { useEffect, useState } from "react"
import api from "../api/axios"

function MovieDetails() {
  const { id } = useParams()
  const [movie, setMovie] = useState(null)

  useEffect(() => {
    const fetchDetails = async () => {
      const response = await api.get(`/movies/${id}`)
      setMovie(response.data)
    }
    fetchDetails()
  }, [id])

  if (!movie) return <div className="page-shell">Loading...</div>

  return (
    <section className="movie-details">
      <h1 className="gold-accent movie-details-title">{movie.title}</h1>
      <p className="movie-details-overview">{movie.overview}</p>
      <div className="movie-meta">
        <p>⭐ Community Score: {movie.vote_average}</p>
        <p>📅 Release Date: {movie.release_date}</p>
        <p>⏱ Runtime: {movie.runtime} mins</p>
      </div>
    </section>
  )
}

export default MovieDetails