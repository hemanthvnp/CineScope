const express = require("express")
const router = express.Router()
const ratingController = require("../controllers/ratingController")
const authMiddleware = require("../middleware/authMiddleware")


router.post("/", authMiddleware, ratingController.submitRating)
router.get("/me", authMiddleware, ratingController.getUserRatings)
router.get("/movie/:movieId", authMiddleware, ratingController.getMovieRatings)

module.exports = router
