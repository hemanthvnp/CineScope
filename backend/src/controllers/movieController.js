const tmdbService = require("../services/tmdbService")

const getTrending = async (req, res) => {
  try {
    const movies = await tmdbService.getTrendingMovies()
    res.json(movies)
  } catch (error) {
    res.status(500).json({ message: "Failed to fetch movies" })
  }
}

const getMovieDetails = async (req, res) => {
  try {
    const { id } = req.params
    const response = await require("axios").get(
      `https://api.themoviedb.org/3/movie/${id}`,
      {
        params: {
          api_key: process.env.TMDB_API_KEY
        }
      }
    )
    res.json(response.data)
  } catch (error) {
    res.status(500).json({ message: "Failed to fetch movie details" })
  }
}

module.exports = {
  getTrending,
  getMovieDetails
}