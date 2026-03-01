import { Routes, Route, useLocation, Navigate } from "react-router-dom"
import Navbar from "./components/Navbar"
import Footer from "./components/Footer"
import Home from "./pages/Home"
import Landing from "./pages/Landing"
import Login from "./pages/Login"
import Register from "./pages/Register"
import Watchlist from "./pages/Watchlist"
import Profile from "./pages/Profile"
import MovieDetails from "./pages/MovieDetails"

const AUTH_STORAGE_KEY = "cinescope-auth"
const TOKEN_STORAGE_KEY = "cinescope-token"

const isAuthenticated = () => {
  return localStorage.getItem(AUTH_STORAGE_KEY) === "true" && Boolean(localStorage.getItem(TOKEN_STORAGE_KEY))
}

function ProtectedRoute({ children }) {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />
  }

  return children
}

function GuestOnlyRoute({ children }) {
  if (isAuthenticated()) {
    return <Navigate to="/home" replace />
  }

  return children
}


function App() {
  const location = useLocation()
  const showFooter = location.pathname !== "/"

  return (
    <div className="app-shell">
      <Navbar />
      <main className="app-main">
        <div key={location.pathname} className="route-transition">
          <Routes location={location}>
            <Route path="/" element={<GuestOnlyRoute><Landing /></GuestOnlyRoute>} />
            <Route path="/login" element={<GuestOnlyRoute><Login /></GuestOnlyRoute>} />
            <Route path="/register" element={<GuestOnlyRoute><Register /></GuestOnlyRoute>} />
            <Route path="/home" element={<ProtectedRoute><Home /></ProtectedRoute>} />
            <Route path="/watchlist" element={<ProtectedRoute><Watchlist /></ProtectedRoute>} />
            <Route path="/profile" element={<ProtectedRoute><Profile /></ProtectedRoute>} />
            <Route path="/movie/:id" element={<ProtectedRoute><MovieDetails /></ProtectedRoute>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>
      {showFooter && <Footer />}
    </div>
  )
}

export default App