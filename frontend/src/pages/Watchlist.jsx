import { useState } from "react";
import "./Watchlist.css";

export default function Watchlist() {
  const [movies, setMovies] = useState([]);
  const [movieName, setMovieName] = useState("");
  const [showInput, setShowInput] = useState(false);

  const addMovie = () => {
    if (movieName.trim() === "") return;

    setMovies([...movies, { name: movieName, confirmed: false }]);
    setMovieName("");
    setShowInput(false);
  };

  const confirmMovie = (index) => {
    const updated = [...movies];
    updated[index].confirmed = true;
    setMovies(updated);
  };

  const deleteMovie = (index) => {
    const updated = movies.filter((_, i) => i !== index);
    setMovies(updated);
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

          <button
            className="add-btn"
            onClick={() => setShowInput(!showInput)}
          >
            +
          </button>

        </div>

        {/* Input Section */}
        {showInput && (
          <div className="input-section">

            <input
              type="text"
              placeholder="Enter movie name..."
              value={movieName}
              onChange={(e) => setMovieName(e.target.value)}
            />

            <button onClick={addMovie}>Add Movie</button>

          </div>
        )}

        {/* Empty state */}
        {movies.length === 0 && (
          <div className="empty">
            🎬 Your watchlist is empty  
            <br />
            Click the <b>+</b> button to add movies.
          </div>
        )}

        {/* Movie List */}
        <ul className="movie-list">

          {movies.map((movie, index) => (
            <li key={index} className="movie-item">

              <span className={movie.confirmed ? "confirmed" : ""}>
                {movie.name}
              </span>

              <div className="buttons">

                {!movie.confirmed && (
                  <button
                    className="confirm"
                    onClick={() => confirmMovie(index)}
                  >
                    ✓
                  </button>
                )}

                <button
                  className="delete"
                  onClick={() => deleteMovie(index)}
                >
                  ✕
                </button>

              </div>

            </li>
          ))}

        </ul>

      </div>

    </div>
  );
}