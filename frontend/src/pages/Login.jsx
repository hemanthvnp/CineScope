import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import CinematicLayout from "../components/CinematicLayout"
import api from "../api/axios"

const AUTH_STORAGE_KEY = "cinescope-auth"
const TOKEN_STORAGE_KEY = "cinescope-token"

function Login() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [statusMessage, setStatusMessage] = useState("")
  const [statusType, setStatusType] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setIsSubmitting(true)
    setStatusMessage("")

    try {
      const response = await api.post("/users/login", { email, password })

      localStorage.setItem(AUTH_STORAGE_KEY, "true")
      localStorage.setItem(TOKEN_STORAGE_KEY, response.data.token)
      setStatusType("success")
      setStatusMessage(response.data.message || "Login successful.")
      navigate("/home")
    } catch (error) {
      setStatusType("error")
      setStatusMessage(error.response?.data?.message || "Login failed.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <CinematicLayout>
      <h1 className="auth-title">Welcome Back</h1>
      <p className="auth-subtitle">
        Continue your cinematic journey.
      </p>

      <form onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Email Address"
          className="register-input"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          required
        />
        <input
          type="password"
          placeholder="Password"
          className="register-input"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        {statusMessage && (
          <p className={`auth-alert ${statusType === "error" ? "error" : "success"}`}>
            {statusMessage}
          </p>
        )}
        <button type="submit" className="register-button">
          {isSubmitting ? "Signing in..." : "Login"}
        </button>
      </form>

      <p className="footer">
        Don’t have an account? <Link to="/register">Join now</Link>
      </p>
    </CinematicLayout>
  )
}

export default Login