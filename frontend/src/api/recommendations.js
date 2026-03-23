import api from "./axios"

/**
 * Recommendation API service
 * Handles calls to the backend for hybrid and genre-based recommendations.
 */

/**
 * Get hybrid recommendations for a user (ML service → genre fallback)
 * @param {string} userId - MongoDB user ID
 * @param {number} limit - Max recommendations
 * @returns {Promise<object>} Recommendations with explanations
 */
export const getHybridRecommendations = async (userId, limit = 20) => {
  const response = await api.get(`/recommendations/${userId}`, {
    params: { limit }
  })
  return response.data
}

/**
 * Get genre-based recommendations (from Node.js recommendation service)
 * @param {string} userId - MongoDB user ID
 * @returns {Promise<object>} Genre-based recommendations
 */
export const getGenreRecommendations = async (userId) => {
  const response = await api.get(`/recommendations/${userId}`, {
    params: { limit: 20 }
  })
  return response.data
}

/**
 * Get trending movies as fallback
 * @returns {Promise<Array>} Trending movies from TMDB
 */
export const getTrendingFallback = async () => {
  const response = await api.get("/movies/trending")
  return response.data
}

/**
 * Get user's genre preferences
 * @param {string} userId - MongoDB user ID
 * @returns {Promise<object>} User preferences
 */
export const getUserPreferences = async (userId) => {
  const response = await api.get(`/recommendations/${userId}/preferences`)
  return response.data
}

/**
 * Get movies by language directly from TMDB
 * @param {string} language - ISO 639-1 language code (e.g., 'ta' for Tamil)
 * @param {string} sort - Sort order: 'popular' or 'top_rated'
 * @returns {Promise<object>} Movies in the specified language
 */
export const getMoviesByLanguage = async (language, sort = "popular") => {
  const response = await api.get(`/movies/language/${language}`, {
    params: { sort }
  })
  return response.data
}

/**
 * Get popular movies
 * @param {number} page - Page number
 * @returns {Promise<object>} Popular movies from TMDB
 */
export const getPopularMovies = async (page = 1) => {
  const response = await api.get("/movies/popular", { params: { page } })
  return response.data
}

/**
 * Get now playing movies
 * @param {number} page - Page number
 * @returns {Promise<object>} Now playing movies from TMDB
 */
export const getNowPlayingMovies = async (page = 1) => {
  const response = await api.get("/movies/now-playing", { params: { page } })
  return response.data
}

/**
 * Get upcoming movies
 * @param {number} page - Page number
 * @returns {Promise<object>} Upcoming movies from TMDB
 */
export const getUpcomingMovies = async (page = 1) => {
  const response = await api.get("/movies/upcoming", { params: { page } })
  return response.data
}
