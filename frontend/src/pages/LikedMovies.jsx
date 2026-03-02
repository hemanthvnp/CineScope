import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import { getLikedMovies, removeMovieFromLiked } from "../api/recommendations";
import "./Watchlist.css";

export default function LikedMovies() {
  const [movies, setMovies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const location = useLocation();

  const loadMovies = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await getLikedMovies();
      setMovies(response.watchlist || []);
    } catch (err) {
      setMovies([]);
      setError(err?.response?.data?.error || err?.message || "Failed to load liked movies");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMovies();
  }, [location]);

  const removeMovie = async (id) => {
    try {
      await removeMovieFromLiked(id);
    } catch (err) {
      setError(err?.response?.data?.error || err?.message || "Failed to remove movie");
    }
    setMovies((prev) => prev.filter((movie) => (movie.movie_id || movie.id) !== id));
  };

  return (
    <div className="page-shell">
      <div className="watchlist-card">
        <div className="header">
          <div className="title-section">
            <h1>Liked Movies</h1>
            <p>Movies you liked in one dedicated collection.</p>
          </div>
        </div>

        {!loading && movies.length === 0 && (
          <div className="empty">
            ❤️ No liked movies yet
            <br />
            Tap Like on any movie card.
          </div>
        )}

        {loading && (
          <div className="empty">Loading your liked movies...</div>
        )}

        {!loading && error && (
          <div className="empty">{error}</div>
        )}

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
                onClick={() => removeMovie(movie.movie_id || movie.id)}
                title="Remove from liked movies"
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
