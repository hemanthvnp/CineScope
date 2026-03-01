import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import api from "../api/axios"

function Profile() {
  const [profile, setProfile] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState("")
  const [needsRelogin, setNeedsRelogin] = useState(false)

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await api.get("/users/me")
        setProfile(response.data.user)
        setErrorMessage("")
        setNeedsRelogin(false)
      } catch (error) {
        if (error.response?.status === 401) {
          localStorage.removeItem("cinescope-token")
          localStorage.removeItem("cinescope-auth")
          setNeedsRelogin(true)
          setErrorMessage("Your session expired. Please log in again.")
        } else {
          setErrorMessage(error.response?.data?.message || "Failed to load profile.")
        }
      } finally {
        setIsLoading(false)
      }
    }

    fetchProfile()
  }, [])

  if (isLoading) {
    return (
      <section className="page-shell">
        <h1 className="gold-accent">Profile</h1>
        <p>Loading your cinephile profile...</p>
      </section>
    )
  }

  if (errorMessage) {
    return (
      <section className="page-shell">
        <h1 className="gold-accent">Profile</h1>
        <p>{errorMessage}</p>
        {needsRelogin && (
          <Link to="/login" className="profile-login-link">
            Go to Login
          </Link>
        )}
      </section>
    )
  }

  return (
    <section className="page-shell">
      <h1 className="gold-accent">Cinephile Profile</h1>

      <div className="profile-hero-card">
        <span className="profile-label">Screen Name</span>
        <h2 className="profile-screen-name">
          @{(profile?.screenName || profile?.name || "cinephile").replace(/\s+/g, "")}
        </h2>
        <p className="profile-subline">This is how CineScope addresses your cinematic identity.</p>
      </div>

      <div className="profile-signature profile-signature-highlight">
        <span>Signature Line</span>
        <p>{profile?.signatureLine || "No signature line yet. Add one that defines your movie vibe."}</p>
      </div>

      <div className="profile-mini-grid">
        <div className="profile-mini-item">
          <span>Identified Genre</span>
          <strong>{profile?.favoriteGenre || "Calibrating..."}</strong>
        </div>
        <div className="profile-mini-item">
          <span>Preferred Era</span>
          <strong>{profile?.favoriteEra || "Calibrating..."}</strong>
        </div>
      </div>

      <div className="profile-wrap-teaser">
        <span>Coming Soon</span>
        <p>
          Your CineScope Wrap: personalized watchlist story, recommendation highlights, and your evolving genre DNA.
        </p>
      </div>
    </section>
  )
}

export default Profile