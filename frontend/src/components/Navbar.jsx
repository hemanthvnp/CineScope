import { useEffect, useState } from "react"
import { Link, useLocation, useNavigate } from "react-router-dom"

const AUTH_STORAGE_KEY = "cinescope-auth"
const TOKEN_STORAGE_KEY = "cinescope-token"

const getAuthState = () => {
  return localStorage.getItem(AUTH_STORAGE_KEY) === "true" && Boolean(localStorage.getItem(TOKEN_STORAGE_KEY))
}

function Navbar() {
  const location = useLocation()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => getAuthState()
  )

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

  return (
    <nav className="site-nav">
      <Link to={isAuthenticated ? "/home" : "/"} className="site-logo-link">
        <h2 className="site-logo">CineScope</h2>
      </Link>

      {!isAuthenticated && (
        <div className="site-links">
          <Link to="/" className="site-link">About</Link>
          <Link to="/login" className="site-link">Sign In</Link>
          <Link to="/register" className="site-link">Create Account</Link>
        </div>
      )}

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