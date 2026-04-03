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
  try {
    const response = await api.get(`/recommendations/${userId}`, {
      params: { limit }
    })
    return response.data
  } catch (error) {
    console.error("Failed to fetch recommendations:", error.message)
    return {
      success: false,
      recommendations: [],
      meta: { error: error.message }
    }
  }
}

const decodeJwtPayload = (token) => {
  try {
    const base64Url = token.split(".")[1]
    if (!base64Url) return null
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/")
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4)
    return JSON.parse(atob(padded))
  } catch {
    return null
  }
}

const getCurrentUserId = async () => {
  const token = localStorage.getItem("cinescope-token")

  if (token) {
    const payload = decodeJwtPayload(token)
    const tokenUserId = payload?.userId || payload?.id || payload?._id || null
    if (tokenUserId) return tokenUserId
  }

  // Fallback: ask backend for current authenticated user
  try {
    const me = await api.get("/users/me")
    const user = me?.data?.user
    return user?.id || user?._id || null
  } catch {
    return null
  }
}

/**
 * Get genre-based recommendations (from Node.js recommendation service)
 * @param {string} userId - MongoDB user ID
 * @returns {Promise<object>} Genre-based recommendations
 */
export const getGenreRecommendations = async (userId) => {
  const response = await api.get(`/recommendations/${userId}/genre-fallback`, {
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

export const addMovieToWatchlist = async (movieId, status = "watchlist", rating = null, userIdArg = null) => {
  const userId = userIdArg || await getCurrentUserId()
  if (!userId) {
    throw new Error("Unable to identify current user")
  }

  // Ensure movieId is a number (TMDB ID)
  const numericMovieId = Number(movieId)
  if (!Number.isFinite(numericMovieId)) {
    throw new Error("Invalid movieId - must be numeric")
  }

  // Use the common recommendation-service endpoint for consistency
  const response = await api.post(`/recommendations/${userId}/watchlist`, {
    movie_id: numericMovieId,
    status,
    rating
  })
  return response.data
}

export const getWatchlist = async (userIdArg = null, status = null) => {
  const userId = userIdArg || await getCurrentUserId()
  if (!userId) {
    throw new Error("Unable to identify current user")
  }

  const response = await api.get(`/recommendations/${userId}/watchlist`, {
    params: status ? { status } : undefined
  })
  return response.data
}

export const removeMovieFromWatchlist = async (movieId, userIdArg = null) => {
  const userId = userIdArg || await getCurrentUserId()
  if (!userId) {
    throw new Error("Unable to identify current user")
  }

  const response = await api.delete(`/recommendations/${userId}/watchlist/${movieId}`)
  return response.data
}

export const addMovieToLiked = async (movieId, userIdArg = null) => {
  return addMovieToWatchlist(movieId, "liked", null, userIdArg)
}

export const getLikedMovies = async (userIdArg = null) => {
  return getWatchlist(userIdArg, "liked")
}

export const removeMovieFromLiked = async (movieId, userIdArg = null) => {
  return removeMovieFromWatchlist(movieId, userIdArg)
}

export const addMovieToDisliked = async (movieId, userIdArg = null) => {
  return addMovieToWatchlist(movieId, "disliked", null, userIdArg)
}

export const removeMovieFromDisliked = async (movieId, userIdArg = null) => {
  return removeMovieFromWatchlist(movieId, userIdArg)
}

/**
 * Get movies by language directly from TMDB
 * @param {string} language - ISO 639-1 language code (e.g., 'ta' for Tamil)
 * @param {string} sort - Sort order: 'popular' or 'top_rated'
 * @returns {Promise<object>} Movies in the specified language
 */
export const getMoviesByLanguage = async (language, sort = "popular", genre = null) => {
  const response = await api.get(`/movies/language/${language}`, {
    params: { sort, genre }
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
