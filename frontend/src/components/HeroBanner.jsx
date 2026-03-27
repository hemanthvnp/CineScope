import { useState, useEffect } from "react"
import api from "../api/axios"

function HeroBanner() {
  const [movies, setMovies] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    const fetchTrending = async () => {
      try {
        const response = await api.get("/movies/trending")
        setMovies(response.data.slice(0, 18))
        setHasError(false)
      } catch (error) {
        console.error("Error fetching movies:", error)
        setHasError(true)
      } finally {
        setIsLoading(false)
      }
    }

    fetchTrending()
  }, [])

  if (isLoading) return <div className="showcase-loading">Loading cinematic showcase...</div>

  if (hasError || !movies.length) {
    return (
      <div className="showcase-loading">
        Unable to load showcase right now. Please check backend/API and refresh.
      </div>
    )
  }

  return (
    <section className="showcase-wall">
      <div className="showcase-grid" aria-hidden="true">
        {movies.map((movie, index) => {
          const imagePath = movie.poster_path || movie.backdrop_path

          if (!imagePath) return null

          return (
            <article key={`${movie.id}-${index}`} className="showcase-card" style={{ animationDelay: `${index * 35}ms` }}>
              <img
                src={`https://image.tmdb.org/t/p/w500${imagePath}`}
                alt={movie.title}
                className="showcase-image"
              />
              <div className="showcase-card-overlay">
                <span>{movie.title}</span>
              </div>
            </article>
          )
        })}
      </div>

      <div className="showcase-shade" />

      <div className="showcase-content">
        <p className="showcase-kicker">CineScope</p>
        <h1>Stories that feel larger than life.</h1>
        <p>
          Explore handpicked cinema across genres with a premium theatre-like browsing experience.
        </p>
      </div>
    </section>
  )
}

export default HeroBanner