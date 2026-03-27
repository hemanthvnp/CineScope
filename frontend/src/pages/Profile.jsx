import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import api from "../api/axios"

const LANGUAGE_OPTIONS = [
  { value: "", label: "No preference" },
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi" },
  { value: "ta", label: "Tamil" },
  { value: "te", label: "Telugu" },
  { value: "ml", label: "Malayalam" },
  { value: "kn", label: "Kannada" },
  { value: "ko", label: "Korean" },
  { value: "ja", label: "Japanese" },
  { value: "fr", label: "French" },
  { value: "es", label: "Spanish" },
  { value: "de", label: "German" },
  { value: "it", label: "Italian" },
  { value: "pt", label: "Portuguese" },
  { value: "zh", label: "Chinese" },
  { value: "ru", label: "Russian" },
]

const ERA_OPTIONS = [
  { value: "", label: "No preference" },
  { value: "2020s", label: "2020s — Current" },
  { value: "2010s", label: "2010s — Streaming Age" },
  { value: "2000s", label: "2000s — Digital Era" },
  { value: "1990s", label: "1990s — Indie Renaissance" },
  { value: "1980s", label: "1980s — Blockbuster Era" },
  { value: "1970s", label: "1970s — New Hollywood" },
  { value: "Classic", label: "Classic — Pre-1970" },
  { value: "Modern", label: "Modern — 2010+" },
]

const GENRE_OPTIONS = [
  "", "Action", "Adventure", "Animation", "Comedy", "Crime",
  "Documentary", "Drama", "Family", "Fantasy", "History",
  "Horror", "Music", "Mystery", "Romance", "Science Fiction",
  "Thriller", "War", "Western", "TV Movie",
]

function Profile() {
  const [profile, setProfile] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState("")
  const [needsRelogin, setNeedsRelogin] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editForm, setEditForm] = useState({})
  const [saveStatus, setSaveStatus] = useState("")
  const [isSaving, setIsSaving] = useState(false)

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

  const startEditing = () => {
    setEditForm({
      screenName: profile?.screenName || "",
      signatureLine: profile?.signatureLine || "",
      favoriteGenre: profile?.favoriteGenre || "",
      favoriteEra: profile?.favoriteEra || "",
      preferredLanguage: profile?.preferredLanguage || "",
    })
    setIsEditing(true)
    setSaveStatus("")
  }

  const handleSave = async () => {
    setIsSaving(true)
    setSaveStatus("")
    try {
      const response = await api.put("/users/me", editForm)
      setProfile(response.data.user)
      setIsEditing(false)
      setSaveStatus("Preferences saved! Recommendations will update on next visit.")
      setTimeout(() => setSaveStatus(""), 5000)
    } catch (error) {
      setSaveStatus(error.response?.data?.message || "Failed to save")
    } finally {
      setIsSaving(false)
    }
  }

  const langLabel = (code) => {
    const found = LANGUAGE_OPTIONS.find(l => l.value === code)
    return found ? found.label : code || "Not set"
  }

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
    <section className="page-shell profile-page">
      <h1 className="gold-accent">Cinephile Profile</h1>

      <div className="profile-hero-card">
        <span className="profile-label">Screen Name</span>
        {isEditing ? (
          <input
            className="profile-edit-input"
            value={editForm.screenName}
            onChange={(e) => setEditForm({ ...editForm, screenName: e.target.value })}
            placeholder="Your screen name"
          />
        ) : (
          <h2 className="profile-screen-name">
            @{(profile?.screenName || profile?.name || "cinephile").replace(/\s+/g, "")}
          </h2>
        )}
        <p className="profile-subline">This is how CineScope addresses your cinematic identity.</p>
      </div>

      <div className="profile-signature profile-signature-highlight">
        <span>Signature Line</span>
        {isEditing ? (
          <input
            className="profile-edit-input"
            value={editForm.signatureLine}
            onChange={(e) => setEditForm({ ...editForm, signatureLine: e.target.value })}
            placeholder="Your movie vibe in one line"
          />
        ) : (
          <p>{profile?.signatureLine || "No signature line yet. Add one that defines your movie vibe."}</p>
        )}
      </div>

      <div className="profile-mini-grid">
        <div className="profile-mini-item">
          <span>🎭 Favorite Genre</span>
          {isEditing ? (
            <select
              className="profile-edit-select"
              value={editForm.favoriteGenre}
              onChange={(e) => setEditForm({ ...editForm, favoriteGenre: e.target.value })}
            >
              {GENRE_OPTIONS.map(g => (
                <option key={g} value={g}>{g || "No preference"}</option>
              ))}
            </select>
          ) : (
            <strong>{profile?.favoriteGenre || "Calibrating..."}</strong>
          )}
        </div>
        <div className="profile-mini-item">
          <span>📅 Preferred Era</span>
          {isEditing ? (
            <select
              className="profile-edit-select"
              value={editForm.favoriteEra}
              onChange={(e) => setEditForm({ ...editForm, favoriteEra: e.target.value })}
            >
              {ERA_OPTIONS.map(o => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          ) : (
            <strong>{profile?.favoriteEra || "Calibrating..."}</strong>
          )}
        </div>
        <div className="profile-mini-item">
          <span>🌐 Preferred Language</span>
          {isEditing ? (
            <select
              className="profile-edit-select"
              value={editForm.preferredLanguage}
              onChange={(e) => setEditForm({ ...editForm, preferredLanguage: e.target.value })}
            >
              {LANGUAGE_OPTIONS.map(l => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          ) : (
            <strong>{langLabel(profile?.preferredLanguage)}</strong>
          )}
        </div>
      </div>

      <div className="profile-actions">
        {isEditing ? (
          <>
            <button
              className="profile-btn profile-btn--save"
              onClick={handleSave}
              disabled={isSaving}
            >
              {isSaving ? "Saving..." : "Save Preferences"}
            </button>
            <button
              className="profile-btn profile-btn--cancel"
              onClick={() => setIsEditing(false)}
              disabled={isSaving}
            >
              Cancel
            </button>
          </>
        ) : (
          <button className="profile-btn profile-btn--edit" onClick={startEditing}>
            ✏️ Edit Preferences
          </button>
        )}
      </div>

      {saveStatus && (
        <p className="profile-save-status">{saveStatus}</p>
      )}

      <div className="profile-wrap-teaser">
        <span>Preference Impact</span>
        <p>
          Your preferences shape how CineScope recommends movies.
          Language preference prioritizes movies in your language (60% of recommendations + score boost).
          Era preference highlights movies from your favorite decade (+10%).
          Favorite genre gives extra weight to matching titles (+10%).
        </p>
      </div>
    </section>
  )
}

export default Profile