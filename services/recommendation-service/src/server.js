require("dotenv").config()
const app = require("./app")
const { connectDB } = require("./config/db")

const PORT = process.env.PORT || 5001
const SERVICE_NAME = process.env.SERVICE_NAME || "recommendation-service"

const startServer = async () => {
  try {
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
