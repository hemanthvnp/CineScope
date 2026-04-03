const mongoose = require("mongoose")
const Genre = require("../models/Genre")
const UserPreference = require("../models/UserPreference")
const UserWatchlist = require("../models/UserWatchlist")
const tmdbClient = require("./tmdbClient")
const logger = require("../utils/logger")

const MIN_ACCEPTABLE_VOTE_AVG = Number(process.env.MIN_ACCEPTABLE_VOTE_AVG || 6.0)
const MIN_ACCEPTABLE_VOTE_COUNT = Number(process.env.MIN_ACCEPTABLE_VOTE_COUNT || 80)

/**
 * Recommendation Service
 *
 * Genre-based movie recommendations powered by TMDB.
 * Movies are fetched live from TMDB rather than stored locally.
 *
 * Algorithm:
 * 1. Fetch user's genre preferences (genre_id -> score mapping)
 * 2. Discover movies on TMDB by the user's preferred genres
 * 3. Score movies based on genre preference match
 * 4. Return top N movies with full TMDB data
 */

/**
 * Get user's genre preferences as a map
 */
const getUserGenrePreferences = async (userId) => {
  const startTime = Date.now()

  const preferences = await UserPreference.find({
    user_id: new mongoose.Types.ObjectId(userId)
  }).lean()

  logger.performance("getUserGenrePreferences", startTime)

  const preferenceMap = new Map()
  for (const pref of preferences) {
    preferenceMap.set(pref.genre_id, pref.score)
  }

  return preferenceMap
}

/**
 * Build a genre_id -> genre_name map
 */
const getGenreNameMap = async () => {
  const genres = await Genre.find({}).select("genre_id genre_name -_id").lean()
  const map = new Map()
  for (const genre of genres) {
    map.set(genre.genre_id, genre.genre_name)
  }
  return map
}

/**
 * Get movie IDs that should be excluded from recommendations
 */
const getExcludedMovieIds = async (userId, options = {}) => {
  const { excludeWatched = true, excludeRated = true } = options

  if (!excludeWatched && !excludeRated) {
    return new Set()
  }

  const statusFilter = []
  if (excludeWatched) statusFilter.push("watched", "watchlist", "liked", "disliked")
  if (excludeRated) statusFilter.push("rated")

  const watchlist = await UserWatchlist.find({
    user_id: new mongoose.Types.ObjectId(userId),
    status: { $in: statusFilter }
  }).select("movie_id").lean()

  return new Set(watchlist.map(item => item.movie_id))
}

/**
 * Calculate recommendation score for a movie based on user's genre preferences
 */
const calculateMovieScore = (movieGenreIds, userPreferences) => {
  if (!movieGenreIds || movieGenreIds.length === 0) {
    return 0
  }

  let score = 0
  for (const genreId of movieGenreIds) {
    if (userPreferences.has(genreId)) {
      score += userPreferences.get(genreId)
    }
  }

  return score
}

/**
 * Calculate strict intersection strength for genre preferences.
 * Higher values mean the movie matches more of the user's chosen genres.
 */
const calculateGenreIntersection = (movieGenreIds, userPreferences) => {
  if (!movieGenreIds || movieGenreIds.length === 0 || userPreferences.size === 0) {
    return {
      matchedPreferenceCount: 0,
      totalPreferenceCount: userPreferences.size,
      isFullIntersection: false
    }
  }

  let matchedPreferenceCount = 0
  for (const preferredGenreId of userPreferences.keys()) {
    if (movieGenreIds.includes(preferredGenreId)) {
      matchedPreferenceCount += 1
    }
  }

  return {
    matchedPreferenceCount,
    totalPreferenceCount: userPreferences.size,
    isFullIntersection: matchedPreferenceCount === userPreferences.size
  }
}

const computeQualityScore = (movie) => {
  const voteAverage = Number(movie?.vote_average || 0)
  const voteCount = Number(movie?.vote_count || 0)
  const popularity = Number(movie?.popularity || 0)

  const ratingNorm = Math.max(0, Math.min(voteAverage / 10, 1))
  const confidenceNorm = Math.min(voteCount / 500, 1)
  const popularityNorm = Math.min(popularity / 200, 1)

  return (0.6 * ratingNorm) + (0.25 * confidenceNorm) + (0.15 * popularityNorm)
}

const passesQualityFloor = (movie) => {
  const voteAverage = Number(movie?.vote_average || 0)
  const voteCount = Number(movie?.vote_count || 0)
  return voteAverage >= MIN_ACCEPTABLE_VOTE_AVG && voteCount >= MIN_ACCEPTABLE_VOTE_COUNT
}

/**
 * Get genre-based movie recommendations for a user.
 * Fetches candidate movies directly from TMDB by preferred genres,
 * scores them, and returns enriched movie data.
 */
const getGenreBasedRecommendations = async (userId, options = {}) => {
  const startTime = Date.now()
  const {
    limit = 20,
    offset = 0,
    excludeWatched = true,
    excludeRated = true
  } = options

  logger.info("Generating recommendations", { userId, options })

  // Step 1: Get user's genre preferences
  const userPreferences = await getUserGenrePreferences(userId)
  const genreNameMap = await getGenreNameMap()

  if (userPreferences.size === 0) {
    logger.warn("No genre preferences found for user", { userId })
    return {
      success: true,
      recommendations: [],
      meta: {
        total: 0,
        limit,
        offset,
        message: "No genre preferences found. Please set your preferences first."
      }
    }
  }

  // Step 2: Get movies to exclude
  const excludedMovieIds = await getExcludedMovieIds(userId, {
    excludeWatched,
    excludeRated
  })

  // Step 3: Fetch candidate movies from TMDB by preferred genres
  const preferredGenreIds = Array.from(userPreferences.keys())
  // Sort genres by preference score (descending) to prioritize top genres
  preferredGenreIds.sort((a, b) => userPreferences.get(b) - userPreferences.get(a))

  // Fetch movies from TMDB for each preferred genre
  const candidateMap = new Map() // movie_id -> { movie, genreIds }

  for (const genreId of preferredGenreIds.slice(0, 5)) { // Top 5 genres
    try {
      const movies = await tmdbClient.discoverByGenre(genreId, 1)
      for (const movie of movies) {
        if (excludedMovieIds.has(movie.id)) continue
        if (!candidateMap.has(movie.id)) {
          candidateMap.set(movie.id, {
            movie,
            genreIds: movie.genre_ids || []
          })
        }
      }
    } catch (error) {
      logger.warn("Failed to fetch genre movies from TMDB", { genreId, error: error.message })
    }
  }

  // Also add some popular movies for diversity
  try {
    const popularMovies = await tmdbClient.fetchPopularMovies(2)
    for (const movie of popularMovies) {
      if (excludedMovieIds.has(movie.id)) continue
      if (!candidateMap.has(movie.id)) {
        candidateMap.set(movie.id, {
          movie,
          genreIds: movie.genre_ids || []
        })
      }
    }
  } catch (error) {
    logger.warn("Failed to fetch popular movies from TMDB", { error: error.message })
  }

  // Step 4: Calculate scores for each candidate
  const movieScores = []
  for (const [movieId, { movie, genreIds }] of candidateMap) {
    const score = calculateMovieScore(genreIds, userPreferences)
    if (score > 0) {
      const intersection = calculateGenreIntersection(genreIds, userPreferences)
      movieScores.push({
        movie_id: movieId,
        score,
        movie,
        genreIds,
        matchedPreferenceCount: intersection.matchedPreferenceCount,
        totalPreferenceCount: intersection.totalPreferenceCount,
        isFullIntersection: intersection.isFullIntersection,
        qualityScore: computeQualityScore(movie),
        passesQualityFloor: passesQualityFloor(movie)
      })
    }
  }

  if (movieScores.length === 0) {
    logger.info("No movie matches found", { userId })
    return {
      success: true,
      recommendations: [],
      meta: {
        total: 0,
        limit,
        offset,
        message: "No matching movies found based on your preferences."
      }
    }
  }

  // Step 5: Sort by strict intersection first, then score
  movieScores.sort((a, b) => {
    if (b.matchedPreferenceCount !== a.matchedPreferenceCount) {
      return b.matchedPreferenceCount - a.matchedPreferenceCount
    }
    if (b.passesQualityFloor !== a.passesQualityFloor) {
      return Number(b.passesQualityFloor) - Number(a.passesQualityFloor)
    }
    if (b.qualityScore !== a.qualityScore) {
      return b.qualityScore - a.qualityScore
    }
    if (b.score !== a.score) return b.score - a.score
    return (b.movie.popularity || 0) - (a.movie.popularity || 0)
  })

  // Step 6: Return paginated results with full movie data from TMDB
  const recommendations = movieScores
    .slice(offset, offset + limit)
    .map(item => {
      // Get actual genre names for the explanation
      const matchingGenreNames = item.genreIds
        .filter(genreId => userPreferences.has(genreId))
        .map(genreId => genreNameMap.get(genreId) || `Genre ${genreId}`)
        .slice(0, 3); // Limit to top 3 genres for readability

      return {
        movie_id: item.movie_id,
        title: item.movie.title,
        overview: item.movie.overview || "",
        poster_path: item.movie.poster_path || "",
        vote_average: item.movie.vote_average || 0,
        vote_count: item.movie.vote_count || 0,
        popularity: item.movie.popularity || 0,
        release_date: item.movie.release_date || "",
        language: item.movie.original_language || "en",
        genre_ids: item.movie.genre_ids || [],
        score: item.score,
        recommendation_score: item.score,
        matching_genres: item.matchedPreferenceCount,
        matching_genre_names: matchingGenreNames,
        matched_preferences: item.matchedPreferenceCount,
        total_preferences: item.totalPreferenceCount,
        is_full_intersection: item.isFullIntersection,
        quality_score: Number(item.qualityScore.toFixed(4)),
        passes_quality_floor: item.passesQualityFloor,
        source: "tmdb_live",
        explanation: {
          type: "genre_match",
          reason: item.isFullIntersection
            ? "Best match: intersects all your selected genre preferences"
            : `Matches ${item.matchedPreferenceCount}/${item.totalPreferenceCount} of your selected genre preferences`,
          score: item.score,
          genres: matchingGenreNames,
          intersection: {
            matched: item.matchedPreferenceCount,
            total: item.totalPreferenceCount,
            full: item.isFullIntersection
          }
        }
      }
    })

  logger.performance("getGenreBasedRecommendations", startTime)
  logger.info("Recommendations generated", {
    userId,
    count: recommendations.length,
    totalScored: movieScores.length
  })

  return {
    success: true,
    recommendations,
    meta: {
      total: movieScores.length,
      returned: recommendations.length,
      limit,
      offset,
      source: "tmdb_live"
    }
  }
}

/**
 * Update user's genre preference
 */
const updateUserPreference = async (userId, genreId, score) => {
  const preference = await UserPreference.findOneAndUpdate(
    {
      user_id: new mongoose.Types.ObjectId(userId),
      genre_id: genreId
    },
    {
      $set: {
        score,
        updated_at: new Date()
      },
      $setOnInsert: {
        user_id: new mongoose.Types.ObjectId(userId),
        genre_id: genreId
      }
    },
    {
      new: true,
      runValidators: true,
      upsert: true
    }
  )

  logger.info("User preference updated", { userId, genreId, score })
  return preference
}

/**
 * Set multiple genre preferences at once
 */
const setUserPreferences = async (userId, preferences) => {
  const bulkOps = preferences.map(pref => ({
    updateOne: {
      filter: {
        user_id: new mongoose.Types.ObjectId(userId),
        genre_id: pref.genre_id
      },
      update: {
        $set: { score: pref.score, updatedAt: new Date() }
      },
      upsert: true
    }
  }))

  const result = await UserPreference.bulkWrite(bulkOps)

  logger.info("User preferences bulk updated", {
    userId,
    count: preferences.length,
    modified: result.modifiedCount,
    upserted: result.upsertedCount
  })

  return {
    success: true,
    modified: result.modifiedCount,
    created: result.upsertedCount
  }
}

/**
 * Get user's current preferences
 */
const getUserPreferences = async (userId) => {
  const preferences = await UserPreference.aggregate([
    {
      $match: { user_id: new mongoose.Types.ObjectId(userId) }
    },
    {
      $lookup: {
        from: "genres",
        localField: "genre_id",
        foreignField: "genre_id",
        as: "genre"
      }
    },
    {
      $unwind: { path: "$genre", preserveNullAndEmptyArrays: true }
    },
    {
      $project: {
        genre_id: 1,
        genre_name: "$genre.genre_name",
        score: 1,
        updatedAt: 1
      }
    },
    {
      $sort: { score: -1 }
    }
  ])

  return preferences
}

/**
 * Get all available genres
 */
const getAllGenres = async () => {
  return Genre.find({}).sort({ genre_name: 1 }).lean()
}

/**
 * Add movie to user's watchlist
 */
const addToWatchlist = async (userId, movieId, status = "watchlist", rating = null) => {
  const numericMovieId = Number(movieId)
  if (!Number.isFinite(numericMovieId)) {
    throw new Error("movie_id must be numeric")
  }

  const entry = await UserWatchlist.findOneAndUpdate(
    {
      user_id: new mongoose.Types.ObjectId(userId),
      movie_id: numericMovieId
    },
    {
      $set: {
        status,
        rating: status === "rated" ? rating : null,
        added_at: new Date()
      },
      $setOnInsert: {
        user_id: new mongoose.Types.ObjectId(userId),
        movie_id: numericMovieId
      }
    },
    {
      new: true,
      runValidators: true,
      upsert: true
    }
  )

  logger.info("Watchlist updated", { userId, movieId, status })
  return entry
}

/**
 * Get user's watchlist items enriched with TMDB movie details
 */
const getUserWatchlist = async (userId, options = {}) => {
  const { limit = 100, offset = 0, status } = options
  const query = {
    user_id: new mongoose.Types.ObjectId(userId)
  }

  if (status) {
    query.status = status
  }

  const watchlistEntries = await UserWatchlist.find(query)
    .sort({ updatedAt: -1 })
    .skip(offset)
    .limit(limit)
    .lean()

  const movieIds = watchlistEntries.map(entry => entry.movie_id)
  const movieMap = await tmdbClient.fetchMoviesByIds(movieIds)

  const items = watchlistEntries.map((entry) => {
    const movie = movieMap.get(entry.movie_id)
    return {
      movie_id: entry.movie_id,
      status: entry.status,
      rating: entry.rating,
      added_at: entry.added_at,
      updatedAt: entry.updatedAt,
      title: movie?.title || "Unknown title",
      overview: movie?.overview || "",
      poster_path: movie?.poster_path || "",
      vote_average: movie?.vote_average || 0,
      vote_count: movie?.vote_count || 0,
      popularity: movie?.popularity || 0,
      release_date: movie?.release_date || "",
      language: movie?.original_language || "en",
      genre_ids: movie?.genre_ids || []
    }
  })

  return {
    success: true,
    watchlist: items,
    meta: {
      total: items.length,
      limit,
      offset
    }
  }
}

/**
 * Remove a movie from user's watchlist
 */
const removeFromWatchlist = async (userId, movieId) => {
  const numericMovieId = Number(movieId)
  if (!Number.isFinite(numericMovieId)) {
    throw new Error("movie_id must be numeric")
  }

  const result = await UserWatchlist.findOneAndDelete({
    user_id: new mongoose.Types.ObjectId(userId),
    movie_id: numericMovieId
  })

  logger.info("Watchlist item removed", { userId, movieId, removed: Boolean(result) })
  return {
    success: true,
    removed: Boolean(result)
  }
}

module.exports = {
  getGenreBasedRecommendations,
  getUserGenrePreferences,
  updateUserPreference,
  setUserPreferences,
  getUserPreferences,
  getAllGenres,
  addToWatchlist,
  getUserWatchlist,
  removeFromWatchlist,
  getExcludedMovieIds,
  calculateMovieScore,
  calculateGenreIntersection
}
