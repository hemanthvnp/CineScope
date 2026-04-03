import { useEffect, useState } from "react"
import { useSearchFilter } from "../context/SearchFilterContext"
import api from "../api/axios"
import SkeletonRow from "./SkeletonRow"
import MovieCard from "./MovieCard"

function MovieRow({ title, search: propSearch, filters: propFilters, movies: propMovies, loading: propLoading }) {
  // Use global search/filter if not provided as props
  const { search, year, genre } = useSearchFilter()
  const [movies, setMovies] = useState([])
  const [loading, setLoading] = useState(true)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    // If movies are provided as props, use them directly
    if (propMovies !== undefined) {
      setMovies(propMovies)
      setLoading(propLoading ?? false)
      return
    }

    // Otherwise, fetch trending movies
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
  }, [propMovies, propLoading])

  // Use props if provided, else global context
  const effectiveSearch = propSearch !== undefined ? propSearch : search
  const effectiveFilters = propFilters !== undefined ? propFilters : { year, genre }

  /* ------------------ CLIENT SIDE FILTERING ------------------ */
  const filteredMovies = movies.filter((movie) => {
    // search by title
    if (effectiveSearch && !movie.title.toLowerCase().includes(effectiveSearch.toLowerCase())) {
      return false
    }

    // filter by year
    if (effectiveFilters.year) {
      const movieYear = movie.release_date?.split("-")[0]
      if (movieYear !== effectiveFilters.year) return false
    }

    // filter by genre (TMDB gives genre_ids)
    if (effectiveFilters.genre && movie.genre_ids) {
      const genreMap = {
        Action: 28,
        Comedy: 35,
        Drama: 18,
        Thriller: 53,
      }

      if (!movie.genre_ids.includes(genreMap[effectiveFilters.genre])) {
        return false
      }
    }

    return true
  })

  if (loading) return <SkeletonRow />

  if (hasError || !filteredMovies.length) {
    return (
      <section className="movie-row">
        <h2>{title}</h2>
        <p className="row-empty-state">No movies match your search.</p>
      </section>
    )
  }

  return (
    <section className="movie-row">
      <h2>{title}</h2>

      <div className="movie-strip">
        {filteredMovies.map((movie, index) => (
          <MovieCard
            key={`${movie.id}-${index}`}
            movie={movie}
            showExplanation={false}
          />
        ))}
      </div>
    </section>
  )
}

export default MovieRow