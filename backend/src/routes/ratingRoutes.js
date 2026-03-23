const express = require("express")
const router = express.Router()
const ratingController = require("../controllers/ratingController")
const authMiddleware = require("../middleware/authMiddleware")

/**
 * Rating Routes
 *
 * POST   /api/ratings            — Submit/update a rating (auth required)
 * GET    /api/ratings/me          — Get current user's ratings (auth required)
 * GET    /api/ratings/movie/:movieId — Get movie rating stats (auth optional via middleware)
 */

router.post("/", authMiddleware, ratingController.submitRating)
router.get("/me", authMiddleware, ratingController.getUserRatings)
router.get("/movie/:movieId", authMiddleware, ratingController.getMovieRatings)

module.exports = router
