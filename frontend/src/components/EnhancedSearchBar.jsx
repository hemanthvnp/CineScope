import { useState, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { useSearchFilter } from "../context/SearchFilterContext"
import api from "../api/axios"

const EnhancedSearchBar = () => {
  const navigate = useNavigate()
  const { search, setSearch, year, setYear, genre, setGenre, setFilters } = useSearchFilter()
  const [suggestions, setSuggestions] = useState([])
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [loading, setLoading] = useState(false)
  const [recentSearches, setRecentSearches] = useState([])
  const [showFilters, setShowFilters] = useState(false)
  const searchRef = useRef(null)
  const inputRef = useRef(null)

  // Load recent searches from localStorage
  useEffect(() => {
    const saved = localStorage.getItem("cinescope-recent-searches")
    if (saved) {
      try {
        setRecentSearches(JSON.parse(saved))
      } catch (e) {
        console.error("Failed to load recent searches:", e)
      }
    }
  }, [])

  // Fetch search suggestions
  useEffect(() => {
    if (search.length < 2) {
      setSuggestions([])
      return
    }

    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const response = await api.get("/movies/search", {
          params: { query: search, page: 1 }
        })
        setSuggestions(response.data.results?.slice(0, 8) || [])
      } catch (error) {
        console.error("Failed to fetch suggestions:", error)
        setSuggestions([])
      } finally {
        setLoading(false)
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [search])

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (searchRef.current && !searchRef.current.contains(event.target)) {
        setShowSuggestions(false)
      }
    }

    document.addEventListener("mousedown", handleClickOutside)
    return () => document.removeEventListener("mousedown", handleClickOutside)
  }, [])

  const handleSearch = (searchTerm = search) => {
    if (!searchTerm.trim()) return

    // Add to recent searches
    const newRecent = [searchTerm, ...recentSearches.filter(s => s !== searchTerm)].slice(0, 5)
    setRecentSearches(newRecent)
    localStorage.setItem("cinescope-recent-searches", JSON.stringify(newRecent))

    // Apply filters and navigate
    setFilters({ year, genre })
    navigate(`/search?q=${encodeURIComponent(searchTerm)}&year=${year}&genre=${genre}`)
    setShowSuggestions(false)
    inputRef.current?.blur()
  }

  const handleSuggestionClick = (movie) => {
    setSearch(movie.title)
    handleSearch(movie.title)
  }

  const handleRecentSearchClick = (term) => {
    setSearch(term)
    handleSearch(term)
  }

  const handleKeyPress = (e) => {
    if (e.key === "Enter") {
      handleSearch()
    } else if (e.key === "Escape") {
      setShowSuggestions(false)
      inputRef.current?.blur()
    }
  }

  const clearFilters = () => {
    setYear("")
    setGenre("")
    setFilters({ year: "", genre: "" })
  }

  const clearRecentSearches = () => {
    setRecentSearches([])
    localStorage.removeItem("cinescope-recent-searches")
  }

  return (
    <div className="enhanced-search-bar" ref={searchRef}>
      <div className="search-input-wrapper">
        <div className="search-input-container">
          <svg className="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle cx="11" cy="11" r="8" strokeWidth="2" />
            <path d="m21 21-4.35-4.35" strokeWidth="2" strokeLinecap="round" />
          </svg>
          
          <input
            ref={inputRef}
            type="text"
            placeholder="Search movies, actors, directors..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onFocus={() => setShowSuggestions(true)}
            onKeyDown={handleKeyPress}
            className="search-input"
          />
          
          {search && (
            <button
              className="clear-search-btn"
              onClick={() => setSearch("")}
              aria-label="Clear search"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M18 6L6 18M6 6l12 12" strokeWidth="2" strokeLinecap="round" />
              </svg>
            </button>
          )}
          
          <button
            className="filter-toggle-btn"
            onClick={() => setShowFilters(!showFilters)}
            aria-label="Toggle filters"
            title={(year || genre) ? "Filters applied" : "Show filters"}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
              <path d="M3 4h18v2H3zM3 10h12v2H3zM3 16h6v2H3z" strokeWidth="2" />
            </svg>
            {(year || genre) && <span className="filter-indicator" />}
          </button>
        </div>

        {/* Suggestions Dropdown */}
        {showSuggestions && (
          <div className="search-suggestions">
            {loading ? (
              <div className="suggestion-loading">
                <div className="skeleton-skeleton" />
                <div className="skeleton-skeleton" />
                <div className="skeleton-skeleton" />
              </div>
            ) : (
              <>
                {/* Recent Searches */}
                {recentSearches.length > 0 && search.length < 2 && (
                  <div className="suggestion-section">
                    <div className="suggestion-header">
                      <span>Recent Searches</span>
                      <button onClick={clearRecentSearches} className="clear-recent-btn">
                        Clear
                      </button>
                    </div>
                    {recentSearches.map((term, index) => (
                      <div
                        key={index}
                        className="suggestion-item recent-search"
                        onClick={() => handleRecentSearchClick(term)}
                      >
                        <svg className="suggestion-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                          <circle cx="12" cy="12" r="10" strokeWidth="1.5" />
                          <path d="M12 6v6l4 2" strokeWidth="1.5" strokeLinecap="round" />
                        </svg>
                        <span>{term}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* Movie Suggestions */}
                {suggestions.length > 0 && (
                  <div className="suggestion-section">
                    <div className="suggestion-header">
                      <span>Movies</span>
                    </div>
                    {suggestions.map((movie) => (
                      <div
                        key={movie.id}
                        className="suggestion-item movie-suggestion"
                        onClick={() => handleSuggestionClick(movie)}
                      >
                        {movie.poster_path ? (
                          <img
                            src={`https://image.tmdb.org/t/p/w92${movie.poster_path}`}
                            alt={movie.title}
                            className="suggestion-poster"
                          />
                        ) : (
                          <div className="suggestion-poster-placeholder" />
                        )}
                        <div className="suggestion-details">
                          <div className="suggestion-title">{movie.title}</div>
                          <div className="suggestion-meta">
                            {movie.release_date && new Date(movie.release_date).getFullYear()}
                            {movie.vote_average && ` • ⭐ ${movie.vote_average.toFixed(1)}`}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* No Results */}
                {search.length >= 2 && !loading && suggestions.length === 0 && (
                  <div className="suggestion-section">
                    <div className="no-results">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                        <circle cx="11" cy="11" r="8" strokeWidth="2" />
                        <path d="m21 21-4.35-4.35" strokeWidth="2" strokeLinecap="round" />
                      </svg>
                      <span>No movies found</span>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {/* Filters Panel */}
      {showFilters && (
        <div className="search-filters-panel">
          <div className="filter-group">
            <label htmlFor="year-filter">Year</label>
            <input
              id="year-filter"
              type="number"
              placeholder="e.g., 2023"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              min="1900"
              max="2030"
              className="filter-input"
            />
          </div>

          <div className="filter-group">
            <label htmlFor="genre-filter">Genre</label>
            <select
              id="genre-filter"
              value={genre}
              onChange={(e) => setGenre(e.target.value)}
              className="filter-select"
            >
              <option value="">All Genres</option>
              <option value="Action">Action</option>
              <option value="Adventure">Adventure</option>
              <option value="Animation">Animation</option>
              <option value="Comedy">Comedy</option>
              <option value="Crime">Crime</option>
              <option value="Documentary">Documentary</option>
              <option value="Drama">Drama</option>
              <option value="Family">Family</option>
              <option value="Fantasy">Fantasy</option>
              <option value="Horror">Horror</option>
              <option value="Music">Music</option>
              <option value="Mystery">Mystery</option>
              <option value="Romance">Romance</option>
              <option value="Science Fiction">Science Fiction</option>
              <option value="TV Movie">TV Movie</option>
              <option value="Thriller">Thriller</option>
              <option value="War">War</option>
              <option value="Western">Western</option>
            </select>
          </div>

          <div className="filter-actions">
            <button onClick={clearFilters} className="clear-filters-btn">
              Clear All
            </button>
            <button onClick={handleSearch} className="apply-filters-btn">
              Search
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default EnhancedSearchBar
