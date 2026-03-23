const mongoose = require("mongoose")
const dns = require('node:dns');
dns.setServers(['1.1.1.1', '8.8.8.8']);
const RETRY_DELAY_MS = 10000
const FALLBACK_RETRY_DELAY_MS = 1000

const uriCandidates = [process.env.MONGO_URI, process.env.MONGO_URI_FALLBACK].filter(Boolean)
let activeUriIndex = 0

const hasSrvDnsError = (error) => {
  const message = error?.message || ""
  return /querySrv|ENOTFOUND|ETIMEOUT|ECONNREFUSED/i.test(message)
}

const connectDB = async () => {
  const mongoUri = uriCandidates[activeUriIndex]

  if (!mongoUri) {
    console.error("MongoDB connection skipped: no connection URI configured")
    return
  }

  try {
    await mongoose.connect(mongoUri, {
      serverSelectionTimeoutMS: 5000
    })
    console.log("MongoDB Connected")
  } catch (error) {
    if (
      hasSrvDnsError(error) &&
      activeUriIndex < uriCandidates.length - 1
    ) {
      activeUriIndex += 1
      console.warn("MongoDB SRV lookup failed. Switching to fallback Mongo URI...")
      setTimeout(connectDB, FALLBACK_RETRY_DELAY_MS)
      return
    }

    console.error("MongoDB connection failed. Retrying in 10s...", error.message)
    setTimeout(connectDB, RETRY_DELAY_MS)
  }
}

module.exports = connectDB