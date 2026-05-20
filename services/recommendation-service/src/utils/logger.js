const SERVICE_NAME = process.env.SERVICE_NAME || "recommendation-service"

const LOG_LEVELS = { ERROR: "ERROR", WARN: "WARN", INFO: "INFO", DEBUG: "DEBUG" }

const formatLog = (level, message, meta = {}) => {
  const timestamp = new Date().toISOString()
  const metaStr = Object.keys(meta).length > 0 ? ` | ${JSON.stringify(meta)}` : ""
  return `[${timestamp}] [${SERVICE_NAME}] [${level}] ${message}${metaStr}`
}

const logger = {
  error: (message, meta = {}) => console.error(formatLog(LOG_LEVELS.ERROR, message, meta)),
  warn: (message, meta = {}) => console.warn(formatLog(LOG_LEVELS.WARN, message, meta)),
  info: (message, meta = {}) => console.log(formatLog(LOG_LEVELS.INFO, message, meta)),
  debug: (message, meta = {}) => {
    if (process.env.NODE_ENV !== "production") {
      console.log(formatLog(LOG_LEVELS.DEBUG, message, meta))
    }
  },
  request: (req, action) => {
    console.log(formatLog(LOG_LEVELS.INFO, `API Request: ${action}`, {
      method: req.method,
      path: req.path,
      params: req.params,
      query: req.query
    }))
  },
  performance: (operation, startTime) => {
    console.log(formatLog(LOG_LEVELS.INFO, `Performance: ${operation}`, {
      duration_ms: Date.now() - startTime
    }))
  }
}

module.exports = logger
