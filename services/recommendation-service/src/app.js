const express = require("express")
const cors = require("cors")
const recommendationRoutes = require("./routes/recommendationRoutes")
const { isMongoConnected } = require("./config/db")

const app = express()

app.use(cors())
app.use(express.json())
app.use((req, res, next) => {
  res.setHeader("X-Service", "recommendation-service")
  next()
})

app.get("/health", (req, res) => {
  const dbConnected = isMongoConnected()
  res.json({
    service: "recommendation-service",
    status: dbConnected ? "healthy" : "degraded",
    db: dbConnected ? "connected" : "disconnected",
    timestamp: new Date().toISOString(),
    version: "1.0.0"
  })
})

app.use("/api/recommendations", recommendationRoutes)

app.use((req, res) => {
  res.status(404).json({
    success: false,
    service: "recommendation-service",
    error: "Endpoint not found"
  })
})

app.use((err, req, res, next) => {
  console.error(`[recommendation-service] Error:`, err.message)
  res.status(500).json({
    success: false,
    service: "recommendation-service",
    error: "Internal server error"
  })
})

module.exports = app
