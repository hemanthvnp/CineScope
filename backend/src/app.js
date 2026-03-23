const express = require("express")
const cors = require("cors")
const axios = require("axios")

const movieRoutes = require("./routes/movieRoutes")
const userRoutes = require("./routes/userRoutes")
const ratingRoutes = require("./routes/ratingRoutes")

const app = express()

// Microservice URLs
const RECOMMENDATION_SERVICE_URL = process.env.RECOMMENDATION_SERVICE_URL || "http://localhost:5001"
const ML_SERVICE_URL = process.env.ML_SERVICE_URL || "http://localhost:8000"

app.use(cors())
app.use(express.json())

// API Routes - Direct
app.use("/api/movies", movieRoutes)
app.use("/api/users", userRoutes)
app.use("/api/ratings", ratingRoutes)

// ML Service Proxy - Hybrid recommendations
// GET /api/recommendations/:userId calls the ML service first, falls back to genre-based
app.get("/api/recommendations/:userId", async (req, res) => {
  const { userId } = req.params
  const limit = parseInt(req.query.limit, 10) || 20

  // Try ML service first (hybrid recommendations)
  try {
    const mlResponse = await axios.post(
      `${ML_SERVICE_URL}/recommend`,
      { userId, limit },
      { timeout: 15000 }
    )
    return res.json(mlResponse.data)
  } catch (mlError) {
    console.warn("[api-gateway] ML service unavailable, falling back to genre-based:", mlError.message)
  }

  // Fallback: proxy to the Node.js recommendation service
  try {
    const fallbackUrl = `${RECOMMENDATION_SERVICE_URL}/api/recommendations/${userId}?limit=${limit}`
    const fallbackResponse = await axios.get(fallbackUrl, { timeout: 10000 })
    return res.json(fallbackResponse.data)
  } catch (fallbackError) {
    if (fallbackError.response) {
      return res.status(fallbackError.response.status).json(fallbackError.response.data)
    }
    return res.status(503).json({
      success: false,
      error: "Recommendation services unavailable"
    })
  }
})

// API Gateway - Proxy other recommendation routes to recommendation microservice
app.use("/api/recommendations", async (req, res) => {
  try {
    const targetUrl = `${RECOMMENDATION_SERVICE_URL}/api/recommendations${req.url}`

    const response = await axios({
      method: req.method,
      url: targetUrl,
      data: req.body,
      headers: {
        "Content-Type": "application/json",
        // Forward auth headers if present
        ...(req.headers.authorization && { Authorization: req.headers.authorization })
      },
      timeout: 30000
    })

    res.status(response.status).json(response.data)
  } catch (error) {
    if (error.response) {
      // Forward error response from microservice
      res.status(error.response.status).json(error.response.data)
    } else if (error.code === "ECONNREFUSED") {
      res.status(503).json({
        success: false,
        error: "Recommendation service unavailable"
      })
    } else {
      res.status(500).json({
        success: false,
        error: "Failed to proxy request to recommendation service"
      })
    }
  }
})

// Health check endpoint
app.get("/api/health", (req, res) => {
  res.json({
    status: "ok",
    service: "api-gateway",
    timestamp: new Date().toISOString()
  })
})

// 404 handler for API routes (Express 5 compatible)
app.use("/api/{*path}", (req, res) => {
  res.status(404).json({ success: false, error: "Endpoint not found" })
})

module.exports = app
