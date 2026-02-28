const posters = [
  "https://image.tmdb.org/t/p/w500/8UlWHLMpgZm9bx6QYh0NFoq67TZ.jpg",
  "https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg",
  "https://image.tmdb.org/t/p/w500/xBHvZcjRiWyobQ9kxBhO6B2dtRI.jpg",
  "https://image.tmdb.org/t/p/w500/rAiYTfKGqDCRIIqo664sY9XZIvQ.jpg",
  "https://image.tmdb.org/t/p/w500/1pdfLvkbY9ohJlCjQH2CZjjYVvJ.jpg"
]

function MovieRow({ title }) {
  return (
    <section style={{ padding: "1.5rem 6rem" }}>
      <h3 style={{ marginBottom: "1rem" }}>{title}</h3>

      <div style={{ display: "flex", gap: "1rem", overflowX: "auto" }}>
        {posters.map((poster) => (
          <div key={poster} style={{ position: "relative", flex: "0 0 auto" }}>
            <img
              src={poster}
              alt="movie"
              style={{
                width: "160px",
                borderRadius: "6px",
                cursor: "pointer",
                transition: "transform 0.3s ease"
              }}
            />

            <div
              style={{
                position: "absolute",
                bottom: "8px",
                left: "8px",
                backgroundColor: "#111",
                padding: "4px 8px",
                borderRadius: "4px",
                fontSize: "0.75rem",
                border: "1px solid #f5c518",
                color: "#f5c518"
              }}
            >
              87% Match
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}

export default MovieRow