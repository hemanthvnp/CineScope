import { useEffect, useState } from "react"
import api from "../api/axios"
import { useNavigate } from "react-router-dom"
import SkeletonRow from "./SkeletonRow"

function MovieRow({ title }) {
  const [movies, setMovies] = useState([])
  const [loading, setLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    const fetchMovies = async () => {
      try {
        const response = await api.get("/movies/trending")
        setMovies(response.data.slice(0, 10))
        setHasError(false)
      } catch (error) {
        console.error(error)
        setHasError(true)
      } finally {
        setLoading(false)
      }
    }

    fetchMovies()
  }, [])

  if (loading) return <SkeletonRow />

  if (hasError || !movies.length) {
    return (
      <section className="movie-row">
        <h2>{title}</h2>
        <p className="row-empty-state">Could not load this row right now.</p>
      </section>
    )
  }

  return (
    <section className="movie-row">
      <h2>{title}</h2>

      <div className="movie-strip">
        {movies.map(movie => (
          <img
            key={movie.id}
            src={`https://image.tmdb.org/t/p/w300${movie.poster_path}`}
            alt={movie.title}
            className="movie-poster"
            onClick={() => navigate(`/movie/${movie.id}`)}
          />
        ))}
      </div>
    </section>
  )
}

export default MovieRow