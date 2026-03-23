/**
 * TMDB API Client for the Recommendation Service
 *
 * Fetches movie data directly from TMDB instead of a local database.
 * Includes in-memory caching with TTL to avoid rate-limit issues.
 */

const axios = require("axios")

const BASE_URL = "https://api.themoviedb.org/3"

const tmdbApi = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: { Accept: "application/json" }
})

// ── Simple in-memory cache ───────────────────────────────────────────
const _cache = new Map()
const CACHE_TTL = 15 * 60 * 1000 // 15 minutes

const cacheGet = (key) => {
  const entry = _cache.get(key)
  if (!entry) return null
  if (Date.now() - entry.ts > CACHE_TTL) {
    _cache.delete(key)
    return null
  }
  return entry.data
}

const cacheSet = (key, data) => {
  _cache.set(key, { data, ts: Date.now() })
}

// ── Retry wrapper ────────────────────────────────────────────────────
const fetchWithRetry = async (url, params, retries = 3) => {
  for (let i = 0; i < retries; i++) {
    try {
      const response = await tmdbApi.get(url, { params })
      return response
    } catch (error) {
      if (i === retries - 1) throw error
      await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)))
    }
  }
}

// ── Public API ───────────────────────────────────────────────────────

/**
 * Fetch multiple pages of popular movies (for building recommendation pool)
 * Returns array of movie objects with genre_ids included
 */
const fetchPopularMovies = async (pages = 5) => {
  const cacheKey = `popular_bulk_${pages}`
  const cached = cacheGet(cacheKey)
  if (cached) return cached

  const allMovies = []
  for (let page = 1; page <= pages; page++) {
    try {
      const response = await fetchWithRetry("/movie/popular", {
        api_key: process.env.TMDB_API_KEY,
        page
      })
      allMovies.push(...response.data.results)
      // Small delay to respect rate limits
      if (page < pages) {
        await new Promise(resolve => setTimeout(resolve, 200))
      }
    } catch (error) {
      console.error(`[tmdbClient] Failed to fetch popular page ${page}:`, error.message)
    }
  }

  cacheSet(cacheKey, allMovies)
  return allMovies
}

/**
 * Fetch movie details by ID from TMDB
 */
const fetchMovieDetails = async (movieId) => {
  const cacheKey = `movie_${movieId}`
  const cached = cacheGet(cacheKey)
  if (cached) return cached

  const response = await fetchWithRetry(`/movie/${movieId}`, {
    api_key: process.env.TMDB_API_KEY
  })

  cacheSet(cacheKey, response.data)
  return response.data
}

/**
 * Fetch details for multiple movie IDs from TMDB
 * Returns a map of movie_id -> movie data
 */
const fetchMoviesByIds = async (movieIds) => {
  const movieMap = new Map()
  const uncachedIds = []

  // Check cache first
  for (const id of movieIds) {
    const cached = cacheGet(`movie_${id}`)
    if (cached) {
      movieMap.set(id, cached)
    } else {
      uncachedIds.push(id)
    }
  }

  // Fetch uncached movies (batch with small delays)
  for (let i = 0; i < uncachedIds.length; i++) {
    try {
      const movie = await fetchMovieDetails(uncachedIds[i])
      movieMap.set(uncachedIds[i], movie)
    } catch (error) {
      console.warn(`[tmdbClient] Failed to fetch movie ${uncachedIds[i]}:`, error.message)
    }
    // Throttle to avoid rate limiting
    if (i < uncachedIds.length - 1 && i % 5 === 4) {
      await new Promise(resolve => setTimeout(resolve, 200))
    }
  }

  return movieMap
}

/**
 * Discover movies by genre from TMDB
 */
const discoverByGenre = async (genreId, page = 1) => {
  const cacheKey = `discover_genre_${genreId}_${page}`
  const cached = cacheGet(cacheKey)
  if (cached) return cached

  const response = await fetchWithRetry("/discover/movie", {
    api_key: process.env.TMDB_API_KEY,
    with_genres: genreId,
    sort_by: "popularity.desc",
    "vote_count.gte": 50,
    page
  })

  cacheSet(cacheKey, response.data.results)
  return response.data.results
}

/**
 * Get trending movies from TMDB
 */
const fetchTrendingMovies = async (limit = 40) => {
  const cacheKey = `trending_${limit}`
  const cached = cacheGet(cacheKey)
  if (cached) return cached

  const results = []
  const pages = Math.ceil(limit / 20)

  for (let page = 1; page <= pages; page++) {
    try {
      const response = await fetchWithRetry("/trending/movie/week", {
        api_key: process.env.TMDB_API_KEY,
        page
      })
      results.push(...response.data.results)
    } catch (error) {
      console.error(`[tmdbClient] Failed to fetch trending page ${page}:`, error.message)
    }
  }

  const sliced = results.slice(0, limit)
  cacheSet(cacheKey, sliced)
  return sliced
}

module.exports = {
  fetchPopularMovies,
  fetchMovieDetails,
  fetchMoviesByIds,
  discoverByGenre,
  fetchTrendingMovies
}
