const express = require("express")
const cors = require("cors")
const axios = require("axios")
const { pipeline } = require("stream")

const movieRoutes = require("./routes/movieRoutes")
const userRoutes = require("./routes/userRoutes")
const ratingRoutes = require("./routes/ratingRoutes")

const app = express()

// Microservice URLs - Normalize by removing trailing slashes
const normalizeUrl = (url) => url ? url.replace(/\/+$/, "") : ""
const RECOMMENDATION_SERVICE_URL = normalizeUrl(process.env.RECOMMENDATION_SERVICE_URL || "http://localhost:5001")
const ML_SERVICE_URL = normalizeUrl(process.env.ML_SERVICE_URL || "http://localhost:8000")
const AI_ORCHESTRATION_URL = normalizeUrl(process.env.AI_ORCHESTRATION_URL || "http://localhost:9000")

app.use(cors())
app.use(express.json())

// Direct routes
app.use("/api/movies", movieRoutes)
app.use("/api/users", userRoutes)
app.use("/api/ratings", ratingRoutes)

// ── AI Orchestration Layer — single intelligent endpoint ─────────────────────
// POST /api/query  { q, userId, locale, options }
app.post("/api/query", async (req, res) => {
  try {
    const response = await axios.post(
      `${AI_ORCHESTRATION_URL}/api/query`,
      req.body,
      {
        timeout: 60_000,
        headers: {
          "Content-Type": "application/json",
          ...(req.headers.authorization && { Authorization: req.headers.authorization }),
        },
      }
    )
    return res.status(response.status).json(response.data)
  } catch (error) {
    if (error.response) {
      return res.status(error.response.status).json(error.response.data)
    }
    if (error.code === "ECONNREFUSED") {
      return res.status(503).json({
        success: false,
        error: "AI orchestration service unavailable",
      })
    }
    return res.status(500).json({
      success: false,
      error: "Failed to process query",
    })
  }
})

const readJsonStream = async (stream) => {
  let body = ""
  for await (const chunk of stream) body += chunk
  try {
    return JSON.parse(body)
  } catch {
    return { success: false, error: body || "Failed to process query" }
  }
}

// Streamed variant: Server-Sent Events piped through as they arrive (intent, results,
// providers, synthesis), so the UI can render each stage without waiting for the last
app.post("/api/query/stream", async (req, res) => {
  const upstreamAbort = new AbortController()
  res.on("close", () => upstreamAbort.abort()) // client went away: stop the upstream query too

  try {
    const upstream = await axios.post(`${AI_ORCHESTRATION_URL}/api/query/stream`, req.body, {
      responseType: "stream",
      timeout: 60_000,
      signal: upstreamAbort.signal,
      headers: {
        "Content-Type": "application/json",
        ...(req.headers.authorization && { Authorization: req.headers.authorization }),
      },
    })
    res.status(upstream.status).set({
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no", // keep nginx in front of the gateway from buffering events
    })
    res.flushHeaders()
    // pipeline, not pipe: if the orchestrator dies mid-stream, pipe() would leave the client's
    // connection open forever; pipeline() closes it, and the client sees the stream end early
    pipeline(upstream.data, res, (err) => {
      if (err && !upstreamAbort.signal.aborted) console.warn("[query/stream] Upstream stream failed:", err.message)
    })
  } catch (error) {
    if (upstreamAbort.signal.aborted) return
    if (error.response) {
      // Validation errors etc. arrive before any event, as a normal JSON body
      return res.status(error.response.status).json(await readJsonStream(error.response.data))
    }
    return res.status(error.code === "ECONNREFUSED" ? 503 : 500).json({
      success: false,
      error: error.code === "ECONNREFUSED" ? "AI orchestration service unavailable" : "Failed to process query",
    })
  }
})

// ── ML Service Proxy — Hybrid recommendations ─────────────────────────────
// GET /api/recommendations/:userId calls ML service first, falls back to genre-based
app.get("/api/recommendations/:userId", async (req, res) => {
  const { userId } = req.params
  const limit = parseInt(req.query.limit, 10) || 20

  // Try ML service first (hybrid recommendations)
  try {
    const mlResponse = await axios.post(
      `${ML_SERVICE_URL}/recommend`,
      { userId, limit },
      { 
        timeout: 60000, // Increased to 60s for deep pool searches
        headers: {
          "Content-Type": "application/json",
          ...(req.headers.authorization && { Authorization: req.headers.authorization })
        }
      }
    )
    return res.json(mlResponse.data)
  } catch (mlError) {
    console.warn("[api-gateway] ML service unavailable, falling back to genre-based:", mlError.message)
  }

  // Fallback: proxy to Node.js recommendation service
  try {
    const fallbackUrl = `${RECOMMENDATION_SERVICE_URL}/api/recommendations/${userId}?limit=${limit}`
    const fallbackResponse = await axios.get(fallbackUrl, { timeout: 30000 })
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
    // Strip /api prefix when proxying to microservices
    const relativePath = req.originalUrl.replace("/api/recommendations", "")
    const targetUrl = `${RECOMMENDATION_SERVICE_URL}/api/recommendations${relativePath}`

    const response = await axios({
      method: req.method,
      url: targetUrl,
      data: req.body,
      headers: {
        "Content-Type": "application/json",
        // Forward auth headers if present
        ...(req.headers.authorization && { Authorization: req.headers.authorization })
      },
      timeout: 60000
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

// ML Service Proxy - Direct access to ML service
app.use("/api/ml-service", async (req, res) => {
  try {
    const targetUrl = `${ML_SERVICE_URL}${req.url}`

    const response = await axios({
      method: req.method,
      url: targetUrl,
      data: req.body,
      headers: {
        "Content-Type": "application/json",
        // Forward auth headers if present
        ...(req.headers.authorization && { Authorization: req.headers.authorization })
      },
      timeout: 60000
    })

    res.status(response.status).json(response.data)
  } catch (error) {
    if (error.response) {
      // Forward error response from microservice
      res.status(error.response.status).json(error.response.data)
    } else if (error.code === "ECONNREFUSED") {
      res.status(503).json({
        success: false,
        error: "ML service unavailable"
      })
    } else {
      res.status(500).json({
        success: false,
        error: "Failed to proxy request to ML service"
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
