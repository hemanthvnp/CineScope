import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import CinematicLayout from "../components/CinematicLayout"
import api from "../api/axios"

const AUTH_STORAGE_KEY = "cinescope-auth"
const TOKEN_STORAGE_KEY = "cinescope-token"

function Register() {
  const [name, setName] = useState("")
  const [screenName, setScreenName] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [favoriteGenre, setFavoriteGenre] = useState("")
  const [favoriteEra, setFavoriteEra] = useState("")
  const [signatureLine, setSignatureLine] = useState("")
  const [otp, setOtp] = useState("")
  const [step, setStep] = useState("details")
  const [statusMessage, setStatusMessage] = useState("")
  const [statusType, setStatusType] = useState("")
  const [smtpFallback, setSmtpFallback] = useState(false)
  const [previewUrl, setPreviewUrl] = useState("")
  const [isSubmitting, setIsSubmitting] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setIsSubmitting(true)
    setStatusMessage("")
    setPreviewUrl("")
    setSmtpFallback(false)

    try {
      const response = await api.post("/users/register/initiate", {
        name,
        screenName,
        email,
        password,
        favoriteGenre,
        favoriteEra,
        signatureLine
      })

      setStep("verify")
      setStatusType("success")
      setStatusMessage(response.data.message || "OTP sent. Please verify your email.")
      setSmtpFallback(Boolean(response.data.smtpFallback))
      setPreviewUrl(response.data.previewUrl || "")
    } catch (error) {
      setStatusType("error")
      setStatusMessage(error.response?.data?.message || "Unable to send OTP. Try again.")
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleVerifyOtp = async (e) => {
    e.preventDefault()
    setIsSubmitting(true)
    setStatusMessage("")

    try {
      const response = await api.post("/users/register/verify", {
        email,
        otp
      })

      setStatusType("success")
      setStatusMessage(response.data.message || "Email verified successfully.")
      localStorage.setItem(AUTH_STORAGE_KEY, "true")
      localStorage.setItem(TOKEN_STORAGE_KEY, response.data.token)
      navigate("/home")
    } catch (error) {
      setStatusType("error")
      setStatusMessage(error.response?.data?.message || "OTP verification failed.")
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <CinematicLayout>
      <h1 className="auth-title">CineScope</h1>
      <p className="auth-subtitle">
        Create your cinephile profile and step into your personal theatre.
      </p>
      <p className="auth-mini-note">Tell us your movie taste so your first recommendations already feel personal.</p>

      <form onSubmit={step === "details" ? handleSubmit : handleVerifyOtp}>
        <input
          type="text"
          placeholder="Full Name"
          className="register-input"
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={step === "verify"}
          required
        />
        <input
          type="text"
          placeholder="Screen Name (example: FrameHunter)"
          className="register-input"
          value={screenName}
          onChange={(event) => setScreenName(event.target.value)}
          disabled={step === "verify"}
        />
        <input
          type="email"
          placeholder="Email Address"
          className="register-input"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={step === "verify"}
          required
        />
        <input
          type="password"
          placeholder="Password"
          className="register-input"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={step === "verify"}
          required
          minLength={6}
        />
        <select
          className="register-select"
          value={favoriteGenre}
          onChange={(event) => setFavoriteGenre(event.target.value)}
          disabled={step === "verify"}
        >
          <option value="">Favorite Genre</option>
          <option value="action">Action</option>
          <option value="thriller">Thriller</option>
          <option value="sci-fi">Sci‑Fi</option>
          <option value="drama">Drama</option>
          <option value="romance">Romance</option>
          <option value="horror">Horror</option>
          <option value="anime">Anime</option>
        </select>
        <select
          className="register-select"
          value={favoriteEra}
          onChange={(event) => setFavoriteEra(event.target.value)}
          disabled={step === "verify"}
        >
          <option value="">Favorite Cinema Era</option>
          <option value="classic">Classic (before 1980)</option>
          <option value="nineties">90s Nostalgia</option>
          <option value="millennium">2000s Blockbuster</option>
          <option value="modern">Modern (2010+)</option>
        </select>
        <textarea
          className="register-textarea"
          placeholder="Your signature movie line or mood in one sentence"
          rows={3}
          value={signatureLine}
          onChange={(event) => setSignatureLine(event.target.value)}
          disabled={step === "verify"}
        />

        {step === "verify" && (
          <input
            type="text"
            placeholder="Enter 6-digit OTP"
            className="register-input otp-input"
            value={otp}
            onChange={(event) => setOtp(event.target.value)}
            required
          />
        )}

        {statusMessage && (
          <>
            <p className={`auth-alert ${statusType === "error" ? "error" : "success"}`}>
              {statusMessage}
            </p>
            {smtpFallback && (
              <p className="auth-debug-note">
                Real SMTP is not configured. This OTP is in test mode.
                {previewUrl && (
                  <>
                    {" "}
                    Open preview:
                    {" "}
                    <a href={previewUrl} target="_blank" rel="noreferrer">View OTP Mail</a>
                  </>
                )}
              </p>
            )}
          </>
        )}

        <div className="auth-actions">
          <button type="submit" className="register-button" disabled={isSubmitting}>
            {isSubmitting
              ? "Please wait..."
              : step === "details"
                ? "Send Verification OTP"
                : "Verify OTP & Create Account"}
          </button>

          {step === "verify" && (
            <button
              type="button"
              className="secondary-auth-button"
              onClick={handleSubmit}
              disabled={isSubmitting}
            >
              Resend OTP
            </button>
          )}
        </div>
      </form>

      <p className="footer">
        Already have an account? <Link to="/login">Sign in</Link>
      </p>
    </CinematicLayout>
  )
}

export default Register