import { useEffect, useState } from "react"
import { useSearchFilter } from "../context/SearchFilterContext"
import api from "../api/axios"
import { useNavigate } from "react-router-dom"
import SkeletonRow from "./SkeletonRow"
import { addMovieToWatchlist, addMovieToLiked } from "../api/recommendations"

function MovieRow({ title, search: propSearch, filters: propFilters }) {
  // Use global search/filter if not provided as props
  const { search, year, genre } = useSearchFilter()
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
                onClick={async e => {
                  e.stopPropagation();
                  try {
                    await addMovieToWatchlist(movie.id, "watchlist");
                    setAddedMovies(new Set([...addedMovies, movie.id]));
                    setTimeout(() => {
                      setAddedMovies(prev => {
                        const updated = new Set(prev);
                        updated.delete(movie.id);
                        return updated;
                      });
                    }, 1500);
                  } catch (err) {
                    console.error("Failed to add to watchlist:", err?.response?.data || err?.message || err);
                  }
                }}
              >
                {addedMovies.has(movie.id) ? "✓ Added!" : "Add to Watchlist"}
              </button>
              <button
                className="add-watchlist-btn"
                title="Like movie"
                onClick={async e => {
                  e.stopPropagation();
                  try {
                    await addMovieToLiked(movie.id);
                  } catch (err) {
                    console.error("Failed to like movie:", err?.response?.data || err?.message || err);
                  }
                }}
              >
                ♥ Like
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