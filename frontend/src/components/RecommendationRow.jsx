import { useRef } from "react"
import MovieCard from "./MovieCard"
import SkeletonRow from "./SkeletonRow"

/**
 * RecommendationRow Component
 *
 * A horizontal scrollable carousel of MovieCard components.
 * Supports left/right scroll arrows and shows loading skeletons.
 *
 * Props:
 *   title - Section heading (e.g., "🎯 Recommended For You")
 *   movies - Array of movie objects with explanation data
 *   loading - Whether the data is still loading
 *   emptyMessage - Message to show when no movies are available
 *   showExplanation - Whether to show explanation badges on cards
 */
function RecommendationRow({
  title,
  movies = [],
  loading = false,
  emptyMessage = "No recommendations available yet.",
  showExplanation = true
}) {
  const stripRef = useRef(null)

  const scroll = (direction) => {
    if (!stripRef.current) return
    const amount = stripRef.current.offsetWidth * 0.7
    stripRef.current.scrollBy({
      left: direction === "left" ? -amount : amount,
      behavior: "smooth"
    })
  }

  if (loading) return <SkeletonRow />

  if (!movies.length) {
    return (
      <section className="rec-row">
        <h2 className="rec-row-title">{title}</h2>
        <p className="rec-row-empty">{emptyMessage}</p>
      </section>
    )
  }

  return (
    <section className="rec-row">
      <h2 className="rec-row-title">{title}</h2>
      <div className="rec-row-container">
        <button
          className="rec-row-arrow rec-row-arrow--left"
          onClick={() => scroll("left")}
          aria-label="Scroll left"
        >
          ‹
        </button>

        <div className="rec-row-strip" ref={stripRef}>
          {movies.map((movie, index) => (
            <MovieCard
              key={`${movie.movie_id || movie.id || "movie"}-${index}`}
              movie={movie}
              explanation={movie.explanation}
              score={movie.score}
              showExplanation={showExplanation}
            />
          ))}
        </div>

        <button
          className="rec-row-arrow rec-row-arrow--right"
          onClick={() => scroll("right")}
          aria-label="Scroll right"
        >
          ›
        </button>
      </div>
    </section>
  )
}

export default RecommendationRow
