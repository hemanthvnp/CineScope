import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import "./Watchlist.css";

export default function Watchlist() {
  const [movies, setMovies] = useState([]);
  const location = useLocation();

  // Function to load movies from localStorage
  const loadMovies = () => {
    const stored = localStorage.getItem('cinescope-watchlist');
    setMovies(stored ? JSON.parse(stored) : []);
  };

  // Load movies whenever this page is navigated to
  useEffect(() => {
    loadMovies();
  }, [location]);

  // Remove movie from watchlist
  const deleteMovie = (id) => {
    const updated = movies.filter((movie) => movie.id !== id);
    setMovies(updated);
    localStorage.setItem('cinescope-watchlist', JSON.stringify(updated));
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
        {movies.length === 0 && (
          <div className="empty">
            🎬 Your watchlist is empty  
            <br />
            Add movies from the home page.
          </div>
        )}

        {/* Movie Grid */}
        <div className="watchlist-movie-grid">
          {movies.map((movie) => (
            <div key={movie.id} className="watchlist-movie-item">
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
                onClick={() => deleteMovie(movie.id)}
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