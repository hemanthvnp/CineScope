import api from "./axios"

/**
 * Rating API service
 * Handles calls to the backend for movie ratings.
 */

/**
 * Submit or update a movie rating
 * @param {number} movieId - TMDB movie ID
 * @param {number} rating - Rating (1-10)
 * @param {string} review - Optional review text
 * @returns {Promise<object>} Updated rating
 */
export const submitRating = async (movieId, rating, review = "") => {
  const response = await api.post("/ratings", { movieId, rating, review })
  return response.data
}

/**
 * Get all ratings by the current user
 * @returns {Promise<object>} User's ratings
 */
export const getUserRatings = async () => {
  const response = await api.get("/ratings/me")
  return response.data
}

/**
 * Get rating stats for a specific movie
 * @param {number} movieId - TMDB movie ID
 * @returns {Promise<object>} Movie rating stats (average, count, userRating)
 */
export const getMovieRatings = async (movieId) => {
  const response = await api.get(`/ratings/movie/${movieId}`)
  return response.data
}
