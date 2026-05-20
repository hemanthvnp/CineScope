import api from "./axios"

export const getHybridRecommendations = async (userId, limit = 20) => {
  try {
    const response = await api.get(`/recommendations/${userId}`, { params: { limit } })
    return response.data
  } catch (error) {
    console.error("Failed to fetch recommendations:", error.message)
    return { success: false, recommendations: [], meta: { error: error.message } }
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
    const id = payload?.userId || payload?.id || payload?._id || null
    if (id) return id
  }
  try {
    const me = await api.get("/users/me")
    const user = me?.data?.user
    return user?.id || user?._id || null
  } catch {
    return null
  }
}

export const getUserPreferences = async (userId) => {
  const response = await api.get(`/recommendations/${userId}/preferences`)
  return response.data
}

export const addMovieToWatchlist = async (movieId, status = "watchlist", rating = null, userIdArg = null) => {
  const userId = userIdArg || await getCurrentUserId()
  if (!userId) throw new Error("Unable to identify current user")

  const numericMovieId = Number(movieId)
  if (!Number.isFinite(numericMovieId)) throw new Error("Invalid movieId — must be numeric")

  const response = await api.post(`/recommendations/${userId}/watchlist`, {
    movie_id: numericMovieId,
    status,
    rating
  })
  return response.data
}

export const getWatchlist = async (userIdArg = null, status = null) => {
  const userId = userIdArg || await getCurrentUserId()
  if (!userId) throw new Error("Unable to identify current user")

  const response = await api.get(`/recommendations/${userId}/watchlist`, {
    params: status ? { status } : undefined
  })
  return response.data
}

export const removeMovieFromWatchlist = async (movieId, userIdArg = null) => {
  const userId = userIdArg || await getCurrentUserId()
  if (!userId) throw new Error("Unable to identify current user")

  const response = await api.delete(`/recommendations/${userId}/watchlist/${movieId}`)
  return response.data
}

export const addMovieToLiked = async (movieId, userIdArg = null) =>
  addMovieToWatchlist(movieId, "liked", null, userIdArg)

export const getLikedMovies = async (userIdArg = null) =>
  getWatchlist(userIdArg, "liked")

export const removeMovieFromLiked = async (movieId, userIdArg = null) =>
  removeMovieFromWatchlist(movieId, userIdArg)

export const addMovieToDisliked = async (movieId, userIdArg = null) =>
  addMovieToWatchlist(movieId, "disliked", null, userIdArg)

export const removeMovieFromDisliked = async (movieId, userIdArg = null) =>
  removeMovieFromWatchlist(movieId, userIdArg)

export const getTrendingFallback = async () => {
  const response = await api.get("/movies/trending")
  return response.data
}

export const getMoviesByLanguage = async (language, sort = "popular", genre = null) => {
  const response = await api.get(`/movies/language/${language}`, { params: { sort, genre } })
  return response.data
}

export const getPopularMovies = async (page = 1) => {
  const response = await api.get("/movies/popular", { params: { page } })
  return response.data
}

export const getNowPlayingMovies = async (page = 1) => {
  const response = await api.get("/movies/now-playing", { params: { page } })
  return response.data
}

export const getUpcomingMovies = async (page = 1) => {
  const response = await api.get("/movies/upcoming", { params: { page } })
  return response.data
}
