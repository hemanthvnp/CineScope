const tmdbService = require("../services/tmdbService")

const getTrending = async (req, res) => {
  try {
    const movies = await tmdbService.getTrendingMovies()
    res.json(movies)
  } catch (error) {
    res.status(500).json({ message: "Failed to fetch trending movies" })
  }
}

const getPopular = async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1
    const data = await tmdbService.getPopularMovies(page)
    res.json(data)
  } catch (error) {
    res.status(500).json({ message: "Failed to fetch popular movies" })
  }
}

const getNowPlaying = async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1
    const data = await tmdbService.getNowPlayingMovies(page)
    res.json(data)
  } catch (error) {
    res.status(500).json({ message: "Failed to fetch now playing movies" })
  }
}

const getUpcoming = async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1
    const data = await tmdbService.getUpcomingMovies(page)
    res.json(data)
  } catch (error) {
    res.status(500).json({ message: "Failed to fetch upcoming movies" })
  }
}

const getTopRated = async (req, res) => {
  try {
    const page = parseInt(req.query.page) || 1
    const data = await tmdbService.getTopRatedMovies(page)
    res.json(data)
  } catch (error) {
    res.status(500).json({ message: "Failed to fetch top rated movies" })
  }
}

const searchMovies = async (req, res) => {
  try {
    const { query } = req.query
    if (!query) {
      return res.status(400).json({ message: "Search query is required" })
    }
    const page = parseInt(req.query.page) || 1
    const data = await tmdbService.searchMovies(query, page)
    res.json(data)
  } catch (error) {
    res.status(500).json({ message: "Failed to search movies" })
  }
}

const getByGenre = async (req, res) => {
  try {
    const { genreId } = req.params
    const page = parseInt(req.query.page) || 1
    const data = await tmdbService.getMoviesByGenre(parseInt(genreId), page)
    res.json(data)
  } catch (error) {
    res.status(500).json({ message: "Failed to fetch movies by genre" })
  }
}

const getMovieDetails = async (req, res) => {
  try {
    const { id } = req.params
    const data = await tmdbService.getMovieDetails(id)
    res.json(data)
  } catch (error) {
    res.status(500).json({ message: "Failed to fetch movie details" })
  }
}

const getMoviesByLanguage = async (req, res) => {
  try {
    const { language } = req.params
    const { page = 1, sort = "popular" } = req.query

    let movies
    if (sort === "top_rated") {
      movies = await tmdbService.getTopRatedByLanguage(language, 20)
    } else {
      movies = await tmdbService.getMoviesByLanguage(language, parseInt(page))
    }

    res.json({
      movies,
      language,
      source: "tmdb_live"
    })
  } catch (error) {
    console.error("Error fetching movies by language:", error.message)
    res.status(500).json({ message: "Failed to fetch movies by language" })
  }
}

const getGenres = async (req, res) => {
  try {
    const genres = await tmdbService.getGenreList()
    res.json({ genres })
  } catch (error) {
    res.status(500).json({ message: "Failed to fetch genres" })
  }
}

module.exports = {
  getTrending,
  getPopular,
  getNowPlaying,
  getUpcoming,
  getTopRated,
  searchMovies,
  getByGenre,
  getMovieDetails,
  getMoviesByLanguage,
  getGenres
}