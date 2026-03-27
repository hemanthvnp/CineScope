/**
 * Database Configuration for Recommendation Service
 */

const mongoose = require("mongoose")
const dns = require("node:dns")

// Use public DNS servers to resolve MongoDB Atlas SRV records
dns.setServers(["1.1.1.1", "8.8.8.8"])

const RETRY_DELAY_MS = 10000
const FALLBACK_RETRY_DELAY_MS = 1000

const uriCandidates = [
  process.env.MONGO_URI,
  process.env.MONGO_URI_FALLBACK
].filter(Boolean)

let activeUriIndex = 0

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const hasSrvDnsError = (error) => {
  const message = error?.message || ""
  return /querySrv|ENOTFOUND|ETIMEOUT|ECONNREFUSED/i.test(message)
}

const connectDB = async () => {
  if (!uriCandidates.length) {
    throw new Error("No MongoDB URI configured for recommendation-service")
  }

  while (true) {
    const mongoUri = uriCandidates[activeUriIndex]

    try {
      await mongoose.connect(mongoUri, {
        serverSelectionTimeoutMS: 5000
      })
      console.log("[recommendation-service] MongoDB Connected")
      return
    } catch (error) {
      if (hasSrvDnsError(error) && activeUriIndex < uriCandidates.length - 1) {
        activeUriIndex += 1
        console.warn("[recommendation-service] MongoDB SRV lookup failed. Switching to fallback...")
        await sleep(FALLBACK_RETRY_DELAY_MS)
        continue
      }

      console.error("[recommendation-service] MongoDB connection failed. Retrying in 10s...", error.message)
      await sleep(RETRY_DELAY_MS)
    }
  }
}

const isMongoConnected = () => mongoose.connection.readyState === 1

module.exports = {
  connectDB,
  isMongoConnected
}
