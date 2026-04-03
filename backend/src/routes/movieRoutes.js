const express = require("express")
const router = express.Router()
const movieController = require("../controllers/movieController")

router.get("/trending", movieController.getTrending)
router.get("/popular", movieController.getPopular)
router.get("/now-playing", movieController.getNowPlaying)
router.get("/upcoming", movieController.getUpcoming)
router.get("/top-rated", movieController.getTopRated)
router.get("/search", movieController.searchMovies)
router.get("/genres", movieController.getGenres)
router.get("/filter/options", movieController.getFilterOptions)
router.get("/filter", movieController.filterMovies)
router.get("/genre/:genreId", movieController.getByGenre)
router.get("/language/:language", movieController.getMoviesByLanguage)
router.get("/:id", movieController.getMovieDetails)

module.exports = router