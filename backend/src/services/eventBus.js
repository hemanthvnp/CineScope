const { createClient } = require("redis")

// Rating events go onto a Redis Stream; the ML service reads them through a consumer group and
// refreshes its models, so a rating write never waits on (or depends on) the ML service.
// Without REDIS_URL, or while Redis is unreachable, publish() returns false and the caller
// falls back to calling the ML service directly.
const STREAM = process.env.RATING_STREAM || "cinescope:ratings"
const MAX_LEN = 1000 // approximate cap: the ML service only needs events it hasn't read yet

let client = null

if (process.env.REDIS_URL) {
  client = createClient({
    url: process.env.REDIS_URL,
    socket: {
      connectTimeout: 5000,
      reconnectStrategy: (retries) => Math.min(retries * 500, 10_000),
    },
    disableOfflineQueue: true, // fail fast and fall back instead of queueing while disconnected
  })
  client.on("error", (err) => console.warn("[events] Redis error:", err.message))
  client.connect().catch((err) => console.warn("[events] Redis connect failed:", err.message))
}

const publish = async (type, fields) => {
  if (!client?.isReady) return false
  try {
    const message = { type, ts: String(Date.now()) }
    for (const [key, value] of Object.entries(fields)) {
      if (value != null) message[key] = String(value)
    }
    await client.xAdd(STREAM, "*", message, {
      TRIM: { strategy: "MAXLEN", strategyModifier: "~", threshold: MAX_LEN },
    })
    return true
  } catch (err) {
    console.warn("[events] Failed to publish", type, err.message)
    return false
  }
}

module.exports = { publish }
