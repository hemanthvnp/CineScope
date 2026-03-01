import { useEffect, useState } from "react"
import HeroBanner from "../components/HeroBanner"
import MovieRow from "../components/MovieRow"
import api from "../api/axios"

function Home() {
  const [profile, setProfile] = useState(null)

  useEffect(() => {
    const nodes = document.querySelectorAll(".reveal-on-scroll")
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible")
            observer.unobserve(entry.target)
          }
        })
      },
      { threshold: 0.12 }
    )

    nodes.forEach((node) => observer.observe(node))

    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await api.get("/users/me")
        setProfile(response.data.user)
      } catch {
        setProfile(null)
      }
    }

    fetchProfile()
  }, [])

  const displayName = (profile?.screenName || profile?.name || "Cinephile").trim()
  const nickname = displayName.replace(/^@/, "").replace(/\s+/g, "")
  const signatureLine = profile?.signatureLine?.trim() || "Start by rating a film you love and we’ll shape your next perfect watch."

  return (
    <div>
      <section className="home-welcome reveal-on-scroll">
        <p className="home-welcome-kicker">Your CineScope Space</p>
        <h1>Hi {nickname}, start with your vibe.</h1>
        <p className="home-welcome-signature">“{signatureLine}”</p>
      </section>

      <div className="reveal-on-scroll"><HeroBanner /></div>
      <div className="reveal-on-scroll"><MovieRow title="🎟 Tonight's Featured Reels" /></div>
      <div className="reveal-on-scroll"><MovieRow title="🎭 Stagecraft Picks For You" /></div>
      <div className="reveal-on-scroll"><MovieRow title="🔥 Intermission Crowd Favorites" /></div>
      <div className="reveal-on-scroll"><MovieRow title="🎬 Director's Spotlight" /></div>
    </div>
  )
}

export default Home