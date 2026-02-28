import { useState } from "react"
import { Link } from "react-router-dom"
import CinematicLayout from "../components/CinematicLayout"

function Register() {
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")

  const handleSubmit = (e) => {
    e.preventDefault()
    console.log({ name, email, password })
  }

  return (
    <CinematicLayout>
      <h1 style={{ color: "#e50914", letterSpacing: "3px" }}>CineScope</h1>
      <p style={{ color: "#aaa", marginBottom: "2rem" }}>
        Discover cinema. Define your taste.
      </p>

      <form onSubmit={handleSubmit}>
        <input type="text" placeholder="Full Name" className="register-input" />
        <input type="email" placeholder="Email Address" className="register-input" />
        <input type="password" placeholder="Password" className="register-input" />
        <button type="submit" className="register-button">
          Create Account
        </button>
      </form>

      <p className="footer">
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </CinematicLayout>
  )
}

export default Register