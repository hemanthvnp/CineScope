const express = require("express")
const router = express.Router()
const recommendationController = require("../controllers/recommendationController")

/**
 * Recommendation Routes
 *
 * Base path: /api/recommendations
 *
 * Routes:
 * - GET /genres - Get all available genres
 * - GET /:userId - Get movie recommendations for a user
 * - GET /:userId/genre-fallback - Get genre-based fallback recommendations
 * - GET /:userId/preferences - Get user's genre preferences
 * - PUT /:userId/preferences - Bulk update user preferences
 * - PATCH /:userId/preferences/:genreId - Update single preference
 * - POST /:userId/watchlist - Add movie to watchlist
 */

// Get all available genres (no auth required)
router.get("/genres", recommendationController.getAllGenres)

// Get recommendations for a user
router.get("/:userId", recommendationController.getRecommendations)

// Get genre-based fallback recommendations
router.get("/:userId/genre-fallback", recommendationController.getRecommendations)

// Get user's current preferences
router.get("/:userId/preferences", recommendationController.getUserPreferences)

// Bulk update user preferences
router.put("/:userId/preferences", recommendationController.updateUserPreferences)

// Update a single genre preference
router.patch("/:userId/preferences/:genreId", recommendationController.updateSinglePreference)

// Add movie to user's watchlist
router.post("/:userId/watchlist", recommendationController.addToWatchlist)
router.get("/:userId/watchlist", recommendationController.getWatchlist)
router.delete("/:userId/watchlist/:movieId", recommendationController.removeFromWatchlist)

module.exports = router
