const express = require("express")
const router = express.Router()
const Watchlist = require("../models/Watchlist")

// ADD movie to watchlist
router.post("/", async (req, res) => {
  try {
    const { movieId, title, year, poster } = req.body

    const exists = await Watchlist.findOne({ movieId })
    if (exists) {
      return res.status(400).json({ message: "Movie already in watchlist" })
    }

    const movie = new Watchlist({
      movieId,
      title,
      year,
      poster
    })

    await movie.save()
    res.status(201).json(movie)
  } catch (err) {
    res.status(500).json({ message: "Failed to add to watchlist" })
  }
})

// GET all watchlist movies
router.get("/", async (req, res) => {
  try {
    const movies = await Watchlist.find().sort({ createdAt: -1 })
    res.json(movies)
  } catch (err) {
    res.status(500).json({ message: "Failed to fetch watchlist" })
  }
})

module.exports = router