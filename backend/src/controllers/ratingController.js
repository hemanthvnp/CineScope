const Rating = require("../models/Rating")
const axios = require("axios")

const RECOMMENDATION_SERVICE_URL = process.env.RECOMMENDATION_SERVICE_URL || "http://localhost:5001"
const ML_SERVICE_URL = process.env.ML_SERVICE_URL || "http://localhost:8000"


const submitRating = async (req, res) => {
  try {
    const userId = req.auth.userId
    const { movieId, rating, review = "" } = req.body

    if (!movieId || typeof movieId !== "number") {
      return res.status(400).json({ message: "Valid movieId (number) is required." })
    }

    if (!rating || rating < 1 || rating > 10) {
      return res.status(400).json({ message: "Rating must be between 1 and 10." })
    }

    // Upsert the rating in our collection
    const ratingDoc = await Rating.findOneAndUpdate(
      { userId, movieId },
      { rating, review, userId, movieId },
      { upsert: true, new: true, setDefaultsOnInsert: true }
    )

    try {
      await axios.post(
        `${RECOMMENDATION_SERVICE_URL}/api/recommendations/${userId}/watchlist`,
        { movie_id: movieId, status: "rated", rating },
        { timeout: 5000 }
      )
    } catch (syncError) {
      console.warn("Failed to sync rating to recommendation service:", syncError.message)
    }

    try {
      axios.post(`${ML_SERVICE_URL}/refresh`, {}, { timeout: 1000 }).catch(() => {})
    } catch (refreshError) {
    }

    return res.status(200).json({
      message: "Rating submitted successfully.",
      rating: ratingDoc
    })
  } catch (error) {
    if (error.code === 11000) {
      return res.status(409).json({ message: "Rating already exists." })
    }
    console.error("Failed to submit rating:", error.message)
    return res.status(500).json({ message: "Failed to submit rating." })
  }
}


const getUserRatings = async (req, res) => {
  try {
    const userId = req.auth.userId
    const ratings = await Rating.find({ userId }).sort({ updatedAt: -1 }).lean()

    return res.status(200).json({ ratings })
  } catch (error) {
    console.error("Failed to get user ratings:", error.message)
    return res.status(500).json({ message: "Failed to fetch ratings." })
  }
}


const getMovieRatings = async (req, res) => {
  try {
    const movieId = parseInt(req.params.movieId, 10)

    if (isNaN(movieId)) {
      return res.status(400).json({ message: "Valid movieId is required." })
    }

    const ratings = await Rating.find({ movieId }).lean()
    const count = ratings.length
    const average = count > 0
      ? ratings.reduce((sum, r) => sum + r.rating, 0) / count
      : 0

    let userRating = null
    if (req.auth?.userId) {
      const myRating = ratings.find(r => r.userId.toString() === req.auth.userId)
      if (myRating) {
        userRating = myRating.rating
      }
    }

    return res.status(200).json({
      movieId,
      average: Math.round(average * 10) / 10,
      count,
      userRating
    })
  } catch (error) {
    console.error("Failed to get movie ratings:", error.message)
    return res.status(500).json({ message: "Failed to fetch movie ratings." })
  }
}

module.exports = {
  submitRating,
  getUserRatings,
  getMovieRatings
}
