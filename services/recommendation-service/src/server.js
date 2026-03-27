/**
 * Recommendation Service - Server Entry Point
 *
 * This is an independent microservice for movie recommendations.
 * It runs on its own port and can be deployed separately.
 */

require("dotenv").config()
const app = require("./app")
const { connectDB } = require("./config/db")

const PORT = process.env.PORT || 5001
const SERVICE_NAME = process.env.SERVICE_NAME || "recommendation-service"

const startServer = async () => {
  try {
    // Ensure DB is connected before serving requests
    await connectDB()

    app.listen(PORT, () => {
      console.log(`[${SERVICE_NAME}] Running on port ${PORT}`)
      console.log(`[${SERVICE_NAME}] Health check: http://localhost:${PORT}/health`)
    })
  } catch (error) {
    console.error(`[${SERVICE_NAME}] Failed to start:`, error.message)
    process.exit(1)
  }
}

startServer()
