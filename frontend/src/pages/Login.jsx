import { useState } from "react"
import { Link } from "react-router-dom"
import CinematicLayout from "../components/CinematicLayout"

function Login() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  const handleSubmit = (e) => {
    e.preventDefault()
    console.log({ email, password })
  }

  return (
    <CinematicLayout>
      <h1 style={{ color: "#e50914", letterSpacing: "3px" }}>Welcome Back</h1>
      <p style={{ color: "#aaa", marginBottom: "2rem" }}>
        Continue your cinematic journey.
      </p>

      <form onSubmit={handleSubmit}>
        <input type="email" placeholder="Email Address" className="register-input" />
        <input type="password" placeholder="Password" className="register-input" />
        <button type="submit" className="register-button">
          Login
        </button>
      </form>

      <p className="footer">
        Don’t have an account? <Link to="/register">Join now</Link>
      </p>
    </CinematicLayout>
  )
}

export default Login