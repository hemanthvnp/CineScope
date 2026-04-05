

const axios = require("axios")

const BASE_URL = "https://api.themoviedb.org/3"

const tmdbApi = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: { Accept: "application/json" }
})
const _cache = new Map()
const CACHE_TTL = 15 * 60 * 1000

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

const fetchMoviesByIds = async (movieIds) => {
  const movieMap = new Map()
  const uncachedIds = movieIds.filter(id => {
    const cached = cacheGet(`movie_${id}`)
    if (cached) {
      movieMap.set(id, cached)
      return false
    }
    return true
  })

  const BATCH_SIZE = 10
  for (let i = 0; i < uncachedIds.length; i += BATCH_SIZE) {
    const batch = uncachedIds.slice(i, i + BATCH_SIZE)
    
    const results = await Promise.all(
      batch.map(async (id) => {
        try {
          const movie = await fetchMovieDetails(id)
          return { id, movie }
        } catch (error) {
          console.warn(`[tmdbClient] Failed to fetch movie ${id}:`, error.message)
          return { id, movie: null }
        }
      })
    )

    for (const { id, movie } of results) {
      if (movie) movieMap.set(id, movie)
    }

    if (i + BATCH_SIZE < uncachedIds.length) {
      await new Promise(resolve => setTimeout(resolve, 300))
    }
  }

  return movieMap
}

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
