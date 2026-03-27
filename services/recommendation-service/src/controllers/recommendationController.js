const recommendationService = require("../services/recommendationService")
const { validateUserId, sanitizeRecommendationOptions, validateScore, validateGenreId } = require("../utils/validators")
const logger = require("../utils/logger")
const { isMongoConnected } = require("../config/db")

/**
 * Recommendation Controller
 * Handles HTTP requests for the recommendation API
 */

/**
 * GET /recommendations/:userId
 * Get personalized movie recommendations for a user based on genre preferences
 */
const getRecommendations = async (req, res) => {
  try {
    logger.request(req, "getRecommendations")
    const { userId } = req.params

    const validation = validateUserId(userId)
    if (!validation.valid) {
      return res.status(400).json({
        success: false,
        error: validation.error
      })
    }

    const options = sanitizeRecommendationOptions(req.query)
    const result = await recommendationService.getGenreBasedRecommendations(userId, options)

    return res.json(result)
  } catch (error) {
    logger.error("Failed to get recommendations", {
      userId: req.params.userId,
      error: error.message
    })

    return res.status(500).json({
      success: false,
      error: "Failed to generate recommendations"
    })
  }
}

/**
 * GET /recommendations/:userId/preferences
 * Get user's current genre preferences
 */
const getUserPreferences = async (req, res) => {
  try {
    logger.request(req, "getUserPreferences")
    const { userId } = req.params

    const validation = validateUserId(userId)
    if (!validation.valid) {
      return res.status(400).json({
        success: false,
        error: validation.error
      })
    }

    const preferences = await recommendationService.getUserPreferences(userId)

    return res.json({
      success: true,
      preferences
    })
  } catch (error) {
    logger.error("Failed to get user preferences", {
      userId: req.params.userId,
      error: error.message
    })

    return res.status(500).json({
      success: false,
      error: "Failed to fetch preferences"
    })
  }
}

/**
 * PUT /recommendations/:userId/preferences
 * Update user's genre preferences (bulk update)
 */
const updateUserPreferences = async (req, res) => {
  try {
    logger.request(req, "updateUserPreferences")
    const { userId } = req.params
    const { preferences } = req.body

    const validation = validateUserId(userId)
    if (!validation.valid) {
      return res.status(400).json({
        success: false,
        error: validation.error
      })
    }

    if (!Array.isArray(preferences) || preferences.length === 0) {
      return res.status(400).json({
        success: false,
        error: "Preferences must be a non-empty array"
      })
    }

    const validatedPrefs = []
    for (const pref of preferences) {
      const genreValidation = validateGenreId(pref.genre_id)
      const scoreValidation = validateScore(pref.score)

      if (!genreValidation.valid) {
        return res.status(400).json({
          success: false,
          error: `Invalid genre_id: ${genreValidation.error}`
        })
      }

      if (!scoreValidation.valid) {
        return res.status(400).json({
          success: false,
          error: `Invalid score: ${scoreValidation.error}`
        })
      }

      validatedPrefs.push({
        genre_id: genreValidation.genreId,
        score: scoreValidation.score
      })
    }

    const result = await recommendationService.setUserPreferences(userId, validatedPrefs)

    return res.json({
      success: true,
      message: "Preferences updated successfully",
      ...result
    })
  } catch (error) {
    logger.error("Failed to update user preferences", {
      userId: req.params.userId,
      error: error.message
    })

    return res.status(500).json({
      success: false,
      error: "Failed to update preferences"
    })
  }
}

/**
 * PATCH /recommendations/:userId/preferences/:genreId
 * Update a single genre preference
 */
const updateSinglePreference = async (req, res) => {
  try {
    logger.request(req, "updateSinglePreference")
    const { userId, genreId } = req.params
    const { score } = req.body

    const userValidation = validateUserId(userId)
    if (!userValidation.valid) {
      return res.status(400).json({
        success: false,
        error: userValidation.error
      })
    }

    const genreValidation = validateGenreId(genreId)
    if (!genreValidation.valid) {
      return res.status(400).json({
        success: false,
        error: genreValidation.error
      })
    }

    const scoreValidation = validateScore(score)
    if (!scoreValidation.valid) {
      return res.status(400).json({
        success: false,
        error: scoreValidation.error
      })
    }

    const preference = await recommendationService.updateUserPreference(
      userId,
      genreValidation.genreId,
      scoreValidation.score
    )

    return res.json({
      success: true,
      preference
    })
  } catch (error) {
    logger.error("Failed to update single preference", {
      userId: req.params.userId,
      genreId: req.params.genreId,
      error: error.message
    })

    return res.status(500).json({
      success: false,
      error: "Failed to update preference"
    })
  }
}

/**
 * GET /recommendations/genres
 * Get all available genres
 */
const getAllGenres = async (req, res) => {
  try {
    logger.request(req, "getAllGenres")

    const genres = await recommendationService.getAllGenres()

    return res.json({
      success: true,
      genres
    })
  } catch (error) {
    logger.error("Failed to get genres", { error: error.message })

    return res.status(500).json({
      success: false,
      error: "Failed to fetch genres"
    })
  }
}

/**
 * POST /recommendations/:userId/watchlist
 * Add a movie to user's watchlist
 */
const addToWatchlist = async (req, res) => {
  try {
    logger.request(req, "addToWatchlist")
    if (!isMongoConnected()) {
      return res.status(503).json({
        success: false,
        error: "Database unavailable. Please try again shortly."
      })
    }
    const { userId } = req.params
    const { movie_id, status = "watchlist", rating } = req.body

    const validation = validateUserId(userId)
    if (!validation.valid) {
      return res.status(400).json({
        success: false,
        error: validation.error
      })
    }

    if (!movie_id || typeof movie_id !== "number") {
      return res.status(400).json({
        success: false,
        error: "Valid movie_id is required"
      })
    }

    const validStatuses = ["watchlist", "watched", "rated", "liked", "disliked"]
    if (!validStatuses.includes(status)) {
      return res.status(400).json({
        success: false,
        error: `Status must be one of: ${validStatuses.join(", ")}`
      })
    }

    if (status === "rated") {
      const scoreValidation = validateScore(rating)
      if (!scoreValidation.valid) {
        return res.status(400).json({
          success: false,
          error: `Rating error: ${scoreValidation.error}`
        })
      }
    }

    const entry = await recommendationService.addToWatchlist(userId, movie_id, status, rating)

    return res.json({
      success: true,
      watchlist: entry
    })
  } catch (error) {
    logger.error("Failed to add to watchlist", {
      userId: req.params.userId,
      error: error.message
    })

    return res.status(500).json({
      success: false,
      error: "Failed to update watchlist",
      details: error.message
    })
  }
}

/**
 * GET /recommendations/:userId/watchlist
 * Get a user's watchlist items
 */
const getWatchlist = async (req, res) => {
  try {
    logger.request(req, "getWatchlist")
    if (!isMongoConnected()) {
      return res.status(503).json({
        success: false,
        error: "Database unavailable. Please try again shortly."
      })
    }
    const { userId } = req.params
    const { limit, offset, status } = req.query

    const validation = validateUserId(userId)
    if (!validation.valid) {
      return res.status(400).json({
        success: false,
        error: validation.error
      })
    }

    const result = await recommendationService.getUserWatchlist(userId, {
      limit: parseInt(limit, 10) || 100,
      offset: parseInt(offset, 10) || 0,
      status
    })

    return res.json(result)
  } catch (error) {
    logger.error("Failed to get watchlist", {
      userId: req.params.userId,
      error: error.message
    })

    return res.status(500).json({
      success: false,
      error: "Failed to fetch watchlist"
    })
  }
}

/**
 * DELETE /recommendations/:userId/watchlist/:movieId
 * Remove a movie from user's watchlist
 */
const removeFromWatchlist = async (req, res) => {
  try {
    logger.request(req, "removeFromWatchlist")
    if (!isMongoConnected()) {
      return res.status(503).json({
        success: false,
        error: "Database unavailable. Please try again shortly."
      })
    }
    const { userId, movieId } = req.params

    const validation = validateUserId(userId)
    if (!validation.valid) {
      return res.status(400).json({
        success: false,
        error: validation.error
      })
    }

    const parsedMovieId = parseInt(movieId, 10)
    if (isNaN(parsedMovieId)) {
      return res.status(400).json({
        success: false,
        error: "Valid movieId is required"
      })
    }

    const result = await recommendationService.removeFromWatchlist(userId, parsedMovieId)
    return res.json(result)
  } catch (error) {
    logger.error("Failed to remove watchlist item", {
      userId: req.params.userId,
      movieId: req.params.movieId,
      error: error.message
    })

    return res.status(500).json({
      success: false,
      error: "Failed to remove watchlist item"
    })
  }
}

module.exports = {
  getRecommendations,
  getUserPreferences,
  updateUserPreferences,
  updateSinglePreference,
  getAllGenres,
  addToWatchlist,
  getWatchlist,
  removeFromWatchlist
}
