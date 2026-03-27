import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { getWatchlist, removeMovieFromWatchlist } from "../api/recommendations";
import "./Watchlist.css";

export default function Watchlist() {
  const [movies, setMovies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const location = useLocation();

  // Function to load movies from localStorage
  const loadMovies = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await getWatchlist(null, "watchlist");
      setMovies(response.watchlist || []);
    } catch (err) {
      setMovies([]);
      setError(err?.response?.data?.error || err?.message || "Failed to load watchlist");
    } finally {
      setLoading(false);
    }
  };

  // Load movies whenever this page is navigated to
  useEffect(() => {
    loadMovies();
  }, [location]);

  // Remove movie from watchlist
  const deleteMovie = async (id) => {
    try {
      await removeMovieFromWatchlist(id);
    } catch (err) {
      setError(err?.response?.data?.error || err?.message || "Failed to remove movie");
    }
    setMovies((prev) => prev.filter((movie) => (movie.movie_id || movie.id) !== id));
  };

  return (
    <div className="page-shell">

      <div className="watchlist-card">

        {/* Header */}
        <div className="header">
          <div className="title-section">
            <h1>Watchlist</h1>
            <p>Save films you want to watch next in one curated shelf.</p>
          </div>
        </div>

        {/* Empty state */}
        {!loading && movies.length === 0 && (
          <div className="empty">
            🎬 Your watchlist is empty  
            <br />
            Add movies from the home page.
          </div>
        )}

        {loading && (
          <div className="empty">
            Loading your watchlist...
          </div>
        )}

        {!loading && error && (
          <div className="empty">{error}</div>
        )}

        {/* Movie Grid */}
        <div className="watchlist-movie-grid">
          {movies.map((movie) => (
            <div key={movie.movie_id || movie.id} className="watchlist-movie-item">
              {movie.poster_path ? (
                <img
                  src={`https://image.tmdb.org/t/p/w300${movie.poster_path}`}
                  alt={movie.title}
                  className="watchlist-poster"
                />
              ) : (
                <div className="watchlist-poster-placeholder">No Image</div>
              )}
              <h3 className="watchlist-movie-title">{movie.title}</h3>
              <button
                className="watchlist-delete-btn"
                onClick={() => deleteMovie(movie.movie_id || movie.id)}
                title="Remove from Watchlist"
              >
                ✕ Remove
              </button>
            </div>
          ))}
        </div>

      </div>

    </div>
  );
}