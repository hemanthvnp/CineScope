/**
 * Simple logging utility for the recommendation service
 * Provides consistent log formatting with timestamps and log levels
 * Can be extended to integrate with external logging services (e.g., Winston, Morgan)
 */

const SERVICE_NAME = process.env.SERVICE_NAME || "recommendation-service"

const LOG_LEVELS = {
  ERROR: "ERROR",
  WARN: "WARN",
  INFO: "INFO",
  DEBUG: "DEBUG"
}

/**
 * Formats a log message with timestamp and level
 * @param {string} level - Log level
 * @param {string} message - Log message
 * @param {object} meta - Additional metadata
 * @returns {string} Formatted log string
 */
const formatLog = (level, message, meta = {}) => {
  const timestamp = new Date().toISOString()
  const metaStr = Object.keys(meta).length > 0 ? ` | ${JSON.stringify(meta)}` : ""
  return `[${timestamp}] [${SERVICE_NAME}] [${level}] ${message}${metaStr}`
}

/**
 * Logger object with methods for each log level
 */
const logger = {
  error: (message, meta = {}) => {
    console.error(formatLog(LOG_LEVELS.ERROR, message, meta))
  },

  warn: (message, meta = {}) => {
    console.warn(formatLog(LOG_LEVELS.WARN, message, meta))
  },

  info: (message, meta = {}) => {
    console.log(formatLog(LOG_LEVELS.INFO, message, meta))
  },

  debug: (message, meta = {}) => {
    if (process.env.NODE_ENV !== "production") {
      console.log(formatLog(LOG_LEVELS.DEBUG, message, meta))
    }
  },

  /**
   * Log request details for API monitoring
   * @param {object} req - Express request object
   * @param {string} action - Action being performed
   */
  request: (req, action) => {
    const meta = {
      method: req.method,
      path: req.path,
      params: req.params,
      query: req.query
    }
    console.log(formatLog(LOG_LEVELS.INFO, `API Request: ${action}`, meta))
  },

  /**
   * Log performance metrics
   * @param {string} operation - Operation name
   * @param {number} startTime - Start time in ms
   */
  performance: (operation, startTime) => {
    const duration = Date.now() - startTime
    console.log(formatLog(LOG_LEVELS.INFO, `Performance: ${operation}`, { duration_ms: duration }))
  }
}

module.exports = logger
