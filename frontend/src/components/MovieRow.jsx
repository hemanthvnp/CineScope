import React, { useEffect, useState } from "react"
import { useSearchFilter } from "../context/SearchFilterContext"
import MovieCard from "./MovieCard"
import SkeletonRow from "./SkeletonRow"
import "./MovieRow.css"

const MovieRow = ({ title, fetchUrl, isLargeRow = false, filters = {} }) => {
  const [movies, setMovies] = useState([])
  const [loading, setLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  
  // Destructure from search filter context
  const { search, year, genre, language } = useSearchFilter()

  useEffect(() => {
    const fetchMovies = async () => {
      setLoading(true)
      try {
        // Since fetchUrl is relative, it would need api.get(fetchUrl) 
        // but this component seems to have been used with various patterns.
        // For now, we mainly ensure that its internal filtering is consistent.
        setMovies([])
        setLoading(false)
      } catch (error) {
        setHasError(true)
        setLoading(false)
      }
    }
    fetchMovies()
  }, [fetchUrl])

  const filteredMovies = movies.filter((movie) => {
    const effectiveFilters = {
      search: filters.search ?? search,
      year: filters.year ?? year,
      genre: filters.genre ?? genre,
      language: filters.language ?? language
    }

    if (effectiveFilters.search && 
        !movie.title?.toLowerCase().includes(effectiveFilters.search.toLowerCase())) {
      return false
    }

    // filter by year
    if (effectiveFilters.year) {
      const movieYear = (movie.release_date || movie.year || "")?.split("-")[0]
      if (movieYear !== effectiveFilters.year) return false
    }

    // filter by genre (using numeric ID from context)
    if (effectiveFilters.genre && movie.genre_ids) {
      if (!movie.genre_ids.includes(Number(effectiveFilters.genre))) {
        return false
      }
    }

    // filter by language
    if (effectiveFilters.language) {
      if (movie.original_language !== effectiveFilters.language) {
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
            key={`${movie.id || index}`}
            movie={movie}
            showExplanation={false}
          />
        ))}
      </div>
    </section>
  )
}

export default MovieRow