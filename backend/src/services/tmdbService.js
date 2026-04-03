const axios = require("axios")

const BASE_URL = "https://api.themoviedb.org/3"

// Create axios instance with timeout and retry config
const tmdbApi = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
  headers: {
    "Accept": "application/json"
  }
})

// ── Simple in-memory cache with TTL ──────────────────────────────────
const _cache = new Map()
const CACHE_TTL = 10 * 60 * 1000 // 10 minutes

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
      console.log(`TMDB request failed, retrying... (${i + 1}/${retries})`)
      await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)))
    }
  }
}

// ── Cached fetch helper ──────────────────────────────────────────────
const cachedFetch = async (cacheKey, url, params) => {
  const cached = cacheGet(cacheKey)
  if (cached) return cached

  const response = await fetchWithRetry(url, {
    api_key: process.env.TMDB_API_KEY,
    ...params
  })
  const data = response.data
  cacheSet(cacheKey, data)
  return data
}

// ── Public API ───────────────────────────────────────────────────────

const getTrendingMovies = async () => {
  const data = await cachedFetch("trending", "/trending/movie/week", {})
  return data.results
}

const getPopularMovies = async (page = 1) => {
  const data = await cachedFetch(`popular_${page}`, "/movie/popular", { page })
  return data
}

const getNowPlayingMovies = async (page = 1) => {
  const data = await cachedFetch(`now_playing_${page}`, "/movie/now_playing", { page })
  return data
}

const getUpcomingMovies = async (page = 1) => {
  const data = await cachedFetch(`upcoming_${page}`, "/movie/upcoming", { page })
  return data
}

const getTopRatedMovies = async (page = 1) => {
  const data = await cachedFetch(`top_rated_${page}`, "/movie/top_rated", { page })
  return data
}

const getMovieDetails = async (movieId) => {
  const data = await cachedFetch(`movie_${movieId}`, `/movie/${movieId}`, {})
  return data
}

const searchMovies = async (query, page = 1) => {
  // Don't cache search results as they change frequently
  const response = await fetchWithRetry("/search/movie", {
    api_key: process.env.TMDB_API_KEY,
    query,
    page
  })
  return response.data
}

const discoverMovies = async (params) => {
  const { 
    page = 1, 
    year, 
    with_genres, 
    language, 
    sort_by = "popularity.desc",
    release_date_gte,
    release_date_lte
  } = params

  const searchParams = {
    page,
    sort_by
  }

  if (year) searchParams.primary_release_year = year
  if (with_genres) searchParams.with_genres = with_genres
  if (language) searchParams.with_original_language = language
  if (release_date_gte) searchParams["release_date.gte"] = release_date_gte
  if (release_date_lte) searchParams["release_date.lte"] = release_date_lte

  const data = await cachedFetch(`discover_${JSON.stringify(searchParams)}`, "/discover/movie", searchParams)
  return data
}

const getMoviesByGenre = async (genreId, page = 1) => {
  const data = await cachedFetch(`genre_${genreId}_${page}`, "/discover/movie", {
    with_genres: genreId,
    sort_by: "popularity.desc",
    page
  })
  return data
}

/**
 * Get popular movies by language from TMDB
 */
const getMoviesByLanguage = async (language, page = 1, with_genres = null) => {
  const searchParams = {
    with_original_language: language,
    sort_by: "popularity.desc",
    page
  }
  
  if (with_genres) {
    searchParams.with_genres = with_genres
  }

  const cacheKey = `lang_${language}_${page}_${with_genres || "any"}`
  const data = await cachedFetch(cacheKey, "/discover/movie", searchParams)

  return data.results.map(movie => ({
    movie_id: movie.id,
    title: movie.title,
    overview: movie.overview,
    poster_path: movie.poster_path,
    vote_average: movie.vote_average,
    vote_count: movie.vote_count,
    popularity: movie.popularity,
    release_date: movie.release_date,
    language: movie.original_language,
    genre_ids: movie.genre_ids,
    source: "tmdb_live"
  }))
}

/**
 * Get top rated movies by language from TMDB
 */
const getTopRatedByLanguage = async (language, limit = 20) => {
  const data = await cachedFetch(`lang_top_${language}`, "/discover/movie", {
    with_original_language: language,
    sort_by: "vote_average.desc",
    "vote_count.gte": 100,
    page: 1
  })

  return data.results.slice(0, limit).map(movie => ({
    movie_id: movie.id,
    title: movie.title,
    overview: movie.overview,
    poster_path: movie.poster_path,
    vote_average: movie.vote_average,
    vote_count: movie.vote_count,
    popularity: movie.popularity,
    release_date: movie.release_date,
    language: movie.original_language,
    genre_ids: movie.genre_ids,
    source: "tmdb_live"
  }))
}

const getGenreList = async () => {
  const data = await cachedFetch("genre_list", "/genre/movie/list", { language: "en-US" })
  return data.genres
}

/**
 * Filter movies by INTERSECTION of genre, language, and era
 * All specified filters must match (AND logic)
 *
 * @param {Object} filters - Filter criteria
 * @param {number} filters.genreId - Genre ID (optional)
 * @param {string} filters.language - Language code like 'en', 'ko' (optional)
 * @param {string} filters.era - Era bucket: 'Classic', 'Old', 'Modern', 'Recent' (optional)
 * @param {number} page - Page number for pagination
 * @returns {Object} - Filtered movies with metadata
 */
const filterMovies = async (filters = {}, page = 1) => {
  const { genreId, language, era } = filters

  // Build TMDB discover params
  const params = {
    sort_by: "popularity.desc",
    page,
    "vote_count.gte": 50
  }

  // Add genre filter
  if (genreId) {
    params.with_genres = genreId
  }

  // Add language filter
  if (language) {
    params.with_original_language = language
  }

  // Add era filter (date range)
  if (era) {
    const eraRanges = {
      "Classic": { start: "1900-01-01", end: "1979-12-31" },
      "Old": { start: "1980-01-01", end: "1999-12-31" },
      "Modern": { start: "2000-01-01", end: "2015-12-31" },
      "Recent": { start: "2016-01-01", end: "2099-12-31" }
    }

    const range = eraRanges[era]
    if (range) {
      params["primary_release_date.gte"] = range.start
      params["primary_release_date.lte"] = range.end
    }
  }

  // Create cache key from filters
  const cacheKey = `filter_${genreId || 'any'}_${language || 'any'}_${era || 'any'}_${page}`

  const data = await cachedFetch(cacheKey, "/discover/movie", params)

  return {
    results: data.results.map(movie => ({
      movie_id: movie.id,
      id: movie.id,
      title: movie.title,
      overview: movie.overview,
      poster_path: movie.poster_path,
      vote_average: movie.vote_average,
      vote_count: movie.vote_count,
      popularity: movie.popularity,
      release_date: movie.release_date,
      language: movie.original_language,
      genre_ids: movie.genre_ids
    })),
    page: data.page,
    total_pages: data.total_pages,
    total_results: data.total_results,
    filters_applied: {
      genre_id: genreId || null,
      language: language || null,
      era: era || null
    }
  }
}

/**
 * Get available filter options (genres, languages, eras)
 */
const getFilterOptions = async () => {
  const genres = await getGenreList()

  return {
    genres: genres,
    languages: [
      { code: "en", name: "English" },
      { code: "ko", name: "Korean" },
      { code: "ja", name: "Japanese" },
      { code: "hi", name: "Hindi" },
      { code: "es", name: "Spanish" },
      { code: "fr", name: "French" },
      { code: "de", name: "German" },
      { code: "zh", name: "Chinese" },
      { code: "it", name: "Italian" },
      { code: "pt", name: "Portuguese" },
      { code: "ru", name: "Russian" },
      { code: "ta", name: "Tamil" },
      { code: "te", name: "Telugu" },
      { code: "ml", name: "Malayalam" },
      { code: "th", name: "Thai" },
      { code: "tr", name: "Turkish" }
    ],
    eras: [
      { id: "Classic", label: "Classic (before 1980)" },
      { id: "Old", label: "Old (1980-1999)" },
      { id: "Modern", label: "Modern (2000-2015)" },
      { id: "Recent", label: "Recent (2016+)" }
    ]
  }
}

module.exports = {
  getTrendingMovies,
  getPopularMovies,
  getNowPlayingMovies,
  getUpcomingMovies,
  getTopRatedMovies,
  getMovieDetails,
  searchMovies,
  discoverMovies,
  getMoviesByGenre,
  getMoviesByLanguage,
  getTopRatedByLanguage,
  getPopularMoviesBulk,
  getGenreList,
  filterMovies,
  getFilterOptions
}