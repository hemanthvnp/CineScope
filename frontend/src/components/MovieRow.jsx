import { useEffect, useState } from "react"
import api from "../api/axios"
import { useNavigate } from "react-router-dom"
import SkeletonRow from "./SkeletonRow"

function MovieRow({ title, search = "", filters = {} }) {
  const [movies, setMovies] = useState([])
  const [loading, setLoading] = useState(true)
  const [hasError, setHasError] = useState(false)
  const [addedMovies, setAddedMovies] = useState(new Set())
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

  /* ------------------ ADD TO WATCHLIST ------------------ */
  const addToWatchlist = async (movie) => {
    try {
      await api.post("/watchlist", {
        movieId: movie.id,
        title: movie.title,
        year: movie.release_date?.split("-")[0],
        poster: movie.poster_path,
      })

      // UI Feedback from HEAD
      setAddedMovies(new Set([...addedMovies, movie.id]))
      setTimeout(() => {
        setAddedMovies(prev => {
          const updated = new Set(prev)
          updated.delete(movie.id)
          return updated
        })
      }, 1500)

    } catch (err) {
      alert("Already in watchlist or error occurred")
    }
  }

  /* ------------------ CLIENT SIDE FILTERING ------------------ */
  const filteredMovies = movies.filter((movie) => {
    // search by title
    if (search && !movie.title.toLowerCase().includes(search.toLowerCase())) {
      return false
    }

    // filter by year
    if (filters.year) {
      const movieYear = movie.release_date?.split("-")[0]
      if (movieYear !== filters.year) return false
    }

    // filter by genre (TMDB gives genre_ids)
    if (filters.genre && movie.genre_ids) {
      const genreMap = {
        Action: 28,
        Comedy: 35,
        Drama: 18,
        Thriller: 53,
      }

      if (!movie.genre_ids.includes(genreMap[filters.genre])) {
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
        {filteredMovies.map((movie) => (
          <div key={movie.id} className="movie-item">
            <img
              src={`https://image.tmdb.org/t/p/w300${movie.poster_path}`}
              alt={movie.title}
              className="movie-poster"
              onClick={() => navigate(`/movie/${movie.id}`)}
              style={{ cursor: 'pointer' }}
            />
            <h3 className="movie-title">{movie.title}</h3>
            <div className="add-watchlist-btn-container">
              <button
                className={`add-watchlist-btn ${addedMovies.has(movie.id) ? 'added-feedback' : ''}`}
                title="Add to Watchlist"
                onClick={(e) => {
                  e.stopPropagation()
                  addToWatchlist(movie)
                }}
              >
                {addedMovies.has(movie.id) ? "✓ Added!" : "Add to Watchlist"}
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

// Add styles for new button layout:
// .add-watchlist-btn-container { display: flex; justify-content: center; margin-top: 8px; }
// .add-watchlist-btn { font-size: 1rem; padding: 0.5rem 1.2rem; border-radius: 24px; background: #222; color: #fff; border: none; cursor: pointer; transition: background 0.2s; }
// .add-watchlist-btn:hover { background: #ff3b30; color: #fff; }
export default MovieRow