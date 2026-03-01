const dns = require('node:dns');
dns.setServers(['1.1.1.1', '8.8.8.8']);
const mongoose = require("mongoose")

const RETRY_DELAY_MS = 10000

const connectDB = async () => {
  try {
    await mongoose.connect(process.env.MONGO_URI, {
      serverSelectionTimeoutMS: 5000
    })
    console.log("MongoDB Connected")
  } catch (error) {
    console.error("MongoDB connection failed. Retrying in 10s...", error.message)
    setTimeout(connectDB, RETRY_DELAY_MS)
  }
}

module.exports = connectDB