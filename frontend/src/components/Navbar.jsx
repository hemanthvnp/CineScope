import { useEffect, useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"

const AUTH_STORAGE_KEY = "cinescope-auth"
const TOKEN_STORAGE_KEY = "cinescope-token"

const getAuthState = () => {
  return (
    localStorage.getItem(AUTH_STORAGE_KEY) === "true" &&
    Boolean(localStorage.getItem(TOKEN_STORAGE_KEY))
  )
}

function Navbar({ onSearch, onFilter }) {
  const location = useLocation()
  const navigate = useNavigate()

  const [menuOpen, setMenuOpen] = useState(false)
  const [isAuthenticated, setIsAuthenticated] = useState(() => getAuthState())

  // search & filter states
  const [search, setSearch] = useState("")
  const [year, setYear] = useState("")
  const [genre, setGenre] = useState("")

  useEffect(() => {
    setIsAuthenticated(getAuthState())
    setMenuOpen(false)
  }, [location.pathname])

  useEffect(() => {
    const handleStorage = () => {
      setIsAuthenticated(getAuthState())
    }

    window.addEventListener("storage", handleStorage)
    return () => window.removeEventListener("storage", handleStorage)
  }, [])

  const handleLogout = () => {
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    localStorage.removeItem(AUTH_STORAGE_KEY)
    setIsAuthenticated(false)
    setMenuOpen(false)
    navigate("/")
  }

  const handleSearchChange = (e) => {
    const value = e.target.value
    setSearch(value)
    onSearch && onSearch(value)
  }

  const applyFilters = () => {
    onFilter && onFilter({ year, genre })
  }

  return (
    <nav className="site-nav">
      <Link to={isAuthenticated ? "/home" : "/"} className="site-logo-link">
        <h2 className="site-logo">CineScope</h2>
      </Link>

      {/* SEARCH + FILTERS (only when logged in & on home) */}
      {isAuthenticated && location.pathname === "/home" && (
        <div className="nav-search">
          <input
            type="text"
            placeholder="Search movies..."
            value={search}
            onChange={handleSearchChange}
          />

          <input
            type="number"
            placeholder="Year"
            value={year}
            onChange={(e) => setYear(e.target.value)}
          />

          <select
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
          >
            <option value="">Genre</option>
            <option value="Action">Action</option>
            <option value="Comedy">Comedy</option>
            <option value="Drama">Drama</option>
            <option value="Thriller">Thriller</option>
          </select>

          <button onClick={applyFilters}>Apply</button>
        </div>
      )}

      {/* PUBLIC LINKS */}
      {!isAuthenticated && (
        <div className="site-links">
          <Link to="/" className="site-link">About</Link>
          <Link to="/login" className="site-link">Sign In</Link>
          <Link to="/register" className="site-link">Create Account</Link>
        </div>
      )}

      {/* AUTHENTICATED MENU */}
      {isAuthenticated && (
        <>
          <button
            type="button"
            className="menu-trigger"
            aria-label="Open navigation menu"
            onClick={() => setMenuOpen(true)}
          >
            ☰
          </button>

          <button
            type="button"
            aria-label="Close menu"
            className={`menu-backdrop ${menuOpen ? "open" : ""}`}
            onClick={() => setMenuOpen(false)}
          />

          <aside className={`side-menu ${menuOpen ? "open" : ""}`}>
            <h3>Menu</h3>

            <Link to="/home" className="side-menu-link" onClick={() => setMenuOpen(false)}>
              Home
            </Link>

            <Link to="/watchlist" className="side-menu-link" onClick={() => setMenuOpen(false)}>
              Watchlist
            </Link>
            <Link to="/liked" className="side-menu-link" onClick={() => setMenuOpen(false)}>
              Liked Movies
            </Link>
            <Link to="/profile" className="side-menu-link" onClick={() => setMenuOpen(false)}>
              Profile
            </Link>

            <button
              type="button"
              className="side-menu-button"
              onClick={handleLogout}
            >
              Logout
            </button>
          </aside>
        </>
      )}
    </nav>
  )
}

export default Navbar