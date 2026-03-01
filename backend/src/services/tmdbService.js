const axios = require("axios")

const BASE_URL = "https://api.themoviedb.org/3"

const getTrendingMovies = async () => {
  const response = await axios.get(
    `${BASE_URL}/trending/movie/week`,
    {
      params: {
        api_key: process.env.TMDB_API_KEY
      }
    }
  )

  return response.data.results
}

module.exports = {
  getTrendingMovies
}