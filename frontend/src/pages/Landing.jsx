import { Link } from "react-router-dom"

const valueProps = [
  {
    title: "Track Every Watch",
    text: "Log films, ratings, and your evolving taste profile in one place."
  },
  {
    title: "Get Smarter Picks",
    text: "Hybrid recommendations blend story similarity with cinephile behavior."
  },
  {
    title: "Know Why It Fits",
    text: "Every recommendation includes a clear reason, not a black-box guess."
  }
]

const quickPoints = [
  "Real-time TMDB catalog",
  "Personal watchlist + ratings",
  "Explainable AI recommendations",
  "Built for serious movie lovers"
]

const featuredMovies = [
  {
    title: "Dune: Part Two",
    poster: "https://image.tmdb.org/t/p/w500/8b8R8l88Qje9dn9OE8PY05Nxl1X.jpg"
  },
  {
    title: "The Batman",
    poster: "https://image.tmdb.org/t/p/w500/74xTEgt7R36Fpooo50r9T25onhq.jpg"
  },
  {
    title: "Poor Things",
    poster: "https://image.tmdb.org/t/p/w500/kCGlIMHnOm8JPXq3rXM6c5wMxcT.jpg"
  },
  {
    title: "Furiosa",
    poster: "https://image.tmdb.org/t/p/w500/iADOJ8Zymht2JPMoy3R7xceZprc.jpg"
  },
  {
    title: "Oppenheimer",
    poster: "https://image.tmdb.org/t/p/w500/ptpr0kGAckfQkJeJIt8st5dglvd.jpg"
  }
]

const productExamples = [
  {
    label: "Track",
    title: "Log Every Film You Watch",
    text: "Example: Rated The Batman ★★★★½ and saved Dune: Part Two to your watchlist."
  },
  {
    label: "Taste",
    title: "Build Your Taste Profile",
    text: "Example: Prefers cerebral sci-fi, neo-noir thrillers, and modern character dramas."
  },
  {
    label: "Recommendation",
    title: "Get Explainable Suggestions",
    text: "Example: Recommended Blade Runner 2049 because of your high ratings for Dune and Arrival."
  }
]

function Landing() {
  return (
    <div className="landing-page sleek-landing">
      <section className="landing-hero sleek-hero">
        <div className="landing-overlay" />

        <div className="landing-content sleek-content">
          <span className="landing-kicker">CineScope</span>
          <h1>Your Personal Cinema Intelligence</h1>
          <p>
            Discover films that match your taste, track your journey, and get recommendations you can actually trust.
          </p>

          <div className="landing-actions">
            <Link to="/register" className="landing-cta landing-cta-primary">
              Join as Cinephile
            </Link>
            <Link to="/login" className="landing-cta landing-cta-secondary">
              Sign In
            </Link>
          </div>

          <div className="sleek-proof-row">
            <span>For true cinephiles</span>
            <span>•</span>
            <span>Hybrid recommendation engine</span>
            <span>•</span>
            <span>Transparent suggestions</span>
          </div>
        </div>
      </section>

      <section className="landing-section sleek-value-wrap">
        <div className="sleek-value-grid">
          {valueProps.map((item) => (
            <article key={item.title} className="sleek-value-card">
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section sleek-movie-strip-wrap">
        <h2 className="landing-section-title">Featured on CineScope</h2>
        <div className="sleek-movie-strip">
          {featuredMovies.map((movie) => (
            <article key={movie.title} className="sleek-movie-card">
              <img src={movie.poster} alt={movie.title} />
              <p>{movie.title}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section sleek-example-wrap">
        <div className="sleek-example-grid">
          {productExamples.map((item) => (
            <article key={item.label} className="sleek-example-card">
              <span>{item.label}</span>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-section sleek-bottom-band">
        <div className="sleek-point-list">
          {quickPoints.map((point) => (
            <span key={point} className="sleek-point-chip">{point}</span>
          ))}
        </div>
        <Link to="/register" className="landing-cta landing-cta-primary">
          Create Free Account
        </Link>
      </section>
    </div>
  )
}

export default Landing
