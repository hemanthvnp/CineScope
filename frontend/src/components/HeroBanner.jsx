function HeroBanner() {
  const movie = {
    title: "Interstellar",
    overview:
      "A team of explorers travel through a wormhole in space.",
    poster:
      "https://image.tmdb.org/t/p/w500/rAiYTfKGqDCRIIqo664sY9XZIvQ.jpg",
    rating: 8.6,
    match: 92,
    reason: "High narrative similarity to films you rated highly."
  }

  return (
    <div
      style={{
        display: "flex",
        gap: "3rem",
        padding: "3rem 6rem",
        alignItems: "center",
        borderBottom: "1px solid #222"
      }}
    >
      <img
        src={movie.poster}
        alt={movie.title}
        style={{
          width: "220px",
          borderRadius: "8px",
          boxShadow: "0 10px 30px rgba(0,0,0,0.6)"
        }}
      />

      <div>
        <h2 className="gold-accent">{movie.title}</h2>
        <p style={{ color: "#aaa", marginBottom: "1rem" }}>
          {movie.overview}
        </p>

        <p style={{ marginBottom: "0.5rem" }}>
            ⭐ Community Score: {movie.rating}
        </p>

        <p style={{ marginBottom: "0.5rem" }}>
            🧠 AI Match: <span className="gold-accent">{movie.match}%</span>
        </p>

        <p style={{ color: "#888", fontSize: "0.9rem" }}>
          {movie.reason}
        </p>
      </div>
    </div>
  )
}

export default HeroBanner