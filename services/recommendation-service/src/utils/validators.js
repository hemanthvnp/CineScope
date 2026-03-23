const mongoose = require("mongoose")

/**
 * Validation utilities for input data
 * Provides consistent validation across the recommendation service
 */

/**
 * Validates if a string is a valid MongoDB ObjectId
 * @param {string} id - ID string to validate
 * @returns {boolean} True if valid ObjectId
 */
const isValidObjectId = (id) => {
  if (!id || typeof id !== "string") {
    return false
  }
  return mongoose.Types.ObjectId.isValid(id)
}

/**
 * Validates userId parameter
 * @param {string} userId - User ID to validate
 * @returns {{ valid: boolean, error?: string }} Validation result
 */
const validateUserId = (userId) => {
  if (!userId) {
    return { valid: false, error: "User ID is required" }
  }

  if (typeof userId !== "string") {
    return { valid: false, error: "User ID must be a string" }
  }

  if (!isValidObjectId(userId)) {
    return { valid: false, error: "Invalid User ID format" }
  }

  return { valid: true }
}

/**
 * Validates pagination parameters
 * @param {number|string} limit - Number of results to return
 * @param {number|string} offset - Number of results to skip
 * @returns {{ valid: boolean, limit: number, offset: number, error?: string }}
 */
const validatePagination = (limit, offset) => {
  const DEFAULT_LIMIT = 20
  const MAX_LIMIT = 100
  const DEFAULT_OFFSET = 0

  let parsedLimit = parseInt(limit, 10)
  let parsedOffset = parseInt(offset, 10)

  // Use defaults if not valid numbers
  if (isNaN(parsedLimit) || parsedLimit < 1) {
    parsedLimit = DEFAULT_LIMIT
  }

  if (isNaN(parsedOffset) || parsedOffset < 0) {
    parsedOffset = DEFAULT_OFFSET
  }

  // Cap limit at maximum
  if (parsedLimit > MAX_LIMIT) {
    parsedLimit = MAX_LIMIT
  }

  return {
    valid: true,
    limit: parsedLimit,
    offset: parsedOffset
  }
}

/**
 * Validates genre ID
 * @param {number|string} genreId - Genre ID to validate
 * @returns {{ valid: boolean, error?: string }}
 */
const validateGenreId = (genreId) => {
  const parsed = parseInt(genreId, 10)

  if (isNaN(parsed) || parsed < 1) {
    return { valid: false, error: "Invalid genre ID" }
  }

  return { valid: true, genreId: parsed }
}

/**
 * Validates preference score
 * @param {number|string} score - Score to validate (0-10)
 * @returns {{ valid: boolean, score?: number, error?: string }}
 */
const validateScore = (score) => {
  const parsed = parseFloat(score)

  if (isNaN(parsed)) {
    return { valid: false, error: "Score must be a number" }
  }

  if (parsed < 0 || parsed > 10) {
    return { valid: false, error: "Score must be between 0 and 10" }
  }

  return { valid: true, score: parsed }
}

/**
 * Sanitizes and validates query options for recommendations
 * @param {object} query - Query parameters
 * @returns {object} Sanitized options
 */
const sanitizeRecommendationOptions = (query = {}) => {
  const { limit, offset } = validatePagination(query.limit, query.offset)

  return {
    limit,
    offset,
    excludeWatched: query.excludeWatched !== "false",
    excludeRated: query.excludeRated !== "false",
    minVoteCount: parseInt(query.minVoteCount, 10) || 10,
    minVoteAverage: parseFloat(query.minVoteAverage) || 0
  }
}

module.exports = {
  isValidObjectId,
  validateUserId,
  validatePagination,
  validateGenreId,
  validateScore,
  sanitizeRecommendationOptions
}
