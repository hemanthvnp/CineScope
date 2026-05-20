const express = require("express")
const router = express.Router()
const recommendationController = require("../controllers/recommendationController")

router.get("/genres", recommendationController.getAllGenres)

router.get("/:userId", recommendationController.getRecommendations)

router.get("/:userId/preferences", recommendationController.getUserPreferences)

router.put("/:userId/preferences", recommendationController.updateUserPreferences)

router.patch("/:userId/preferences/:genreId", recommendationController.updateSinglePreference)

router.post("/:userId/watchlist", recommendationController.addToWatchlist)
router.get("/:userId/watchlist", recommendationController.getWatchlist)
router.delete("/:userId/watchlist/:movieId", recommendationController.removeFromWatchlist)

module.exports = router
