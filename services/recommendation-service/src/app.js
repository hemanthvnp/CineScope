/**
 * Recommendation Service - Express Application
 *
 * Microservice for genre-based movie recommendations.
 * Phase 1: Genre-based scoring
 * Future phases: TF-IDF, SVD, hybrid approaches
 */

const express = require("express")
const cors = require("cors")
const recommendationRoutes = require("./routes/recommendationRoutes")

const app = express()

// Middleware
app.use(cors())
app.use(express.json())

// Service info middleware - adds service name to responses
app.use((req, res, next) => {
  res.setHeader("X-Service", "recommendation-service")
  next()
})

// Health check endpoint
app.get("/health", (req, res) => {
  res.json({
    service: "recommendation-service",
    status: "healthy",
    timestamp: new Date().toISOString(),
    version: "1.0.0"
  })
})

// API Routes
app.use("/api/recommendations", recommendationRoutes)

// 404 handler
app.use((req, res) => {
  res.status(404).json({
    success: false,
    service: "recommendation-service",
    error: "Endpoint not found"
  })
})

// Error handler
app.use((err, req, res, next) => {
  console.error(`[recommendation-service] Error:`, err.message)
  res.status(500).json({
    success: false,
    service: "recommendation-service",
    error: "Internal server error"
  })
})

module.exports = app
