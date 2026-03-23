import { useState } from "react"

/**
 * StarRating Component
 *
 * Interactive 1-10 star rating widget with hover preview.
 * Displays filled/empty stars and reports the selected rating.
 *
 * Props:
 *   currentRating - Current rating value (0 = unrated)
 *   onRate - Callback function(rating) when user clicks a star
 *   disabled - Whether the widget is non-interactive
 *   size - Size in rem (default: 1.4)
 */
function StarRating({ currentRating = 0, onRate, disabled = false, size = 1.4 }) {
  const [hoverRating, setHoverRating] = useState(0)
  const maxStars = 10

  const displayRating = hoverRating || currentRating

  const handleClick = (value) => {
    if (disabled) return
    if (onRate) onRate(value)
  }

  return (
    <div className="star-rating" style={{ fontSize: `${size}rem` }}>
      <div className="star-rating-stars">
        {Array.from({ length: maxStars }, (_, i) => {
          const value = i + 1
          const isFilled = value <= displayRating

          return (
            <button
              key={value}
              type="button"
              className={`star-rating-star ${isFilled ? "star-rating-star--filled" : ""} ${disabled ? "star-rating-star--disabled" : ""}`}
              onClick={() => handleClick(value)}
              onMouseEnter={() => !disabled && setHoverRating(value)}
              onMouseLeave={() => !disabled && setHoverRating(0)}
              aria-label={`Rate ${value} out of ${maxStars}`}
              disabled={disabled}
            >
              {isFilled ? "★" : "☆"}
            </button>
          )
        })}
      </div>
      {displayRating > 0 && (
        <span className="star-rating-label">{displayRating}/{maxStars}</span>
      )}
    </div>
  )
}

export default StarRating
