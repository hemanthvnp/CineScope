/**
 * Database Seed Script for Recommendation Service
 * Seeds TMDB genre IDs into the local genres collection.
 * Movies are no longer stored locally — they are fetched from TMDB at runtime.
 *
 * Usage: npm run seed
 */

require("dotenv").config()
const mongoose = require("mongoose")
const dns = require("node:dns")
const Genre = require("../models/Genre")

// Use public DNS servers to resolve MongoDB Atlas SRV records
dns.setServers(["1.1.1.1", "8.8.8.8"])

// TMDB genre IDs (standard across TMDB API)
const TMDB_GENRES = [
  { genre_id: 28, genre_name: "Action" },
  { genre_id: 12, genre_name: "Adventure" },
  { genre_id: 16, genre_name: "Animation" },
  { genre_id: 35, genre_name: "Comedy" },
  { genre_id: 80, genre_name: "Crime" },
  { genre_id: 99, genre_name: "Documentary" },
  { genre_id: 18, genre_name: "Drama" },
  { genre_id: 10751, genre_name: "Family" },
  { genre_id: 14, genre_name: "Fantasy" },
  { genre_id: 36, genre_name: "History" },
  { genre_id: 27, genre_name: "Horror" },
  { genre_id: 10402, genre_name: "Music" },
  { genre_id: 9648, genre_name: "Mystery" },
  { genre_id: 10749, genre_name: "Romance" },
  { genre_id: 878, genre_name: "Science Fiction" },
  { genre_id: 10770, genre_name: "TV Movie" },
  { genre_id: 53, genre_name: "Thriller" },
  { genre_id: 10752, genre_name: "War" },
  { genre_id: 37, genre_name: "Western" }
]

/**
 * Seed genres into the database
 */
const seedGenres = async () => {
  console.log("[recommendation-service] Seeding genres...")

  for (const genre of TMDB_GENRES) {
    await Genre.findOneAndUpdate(
      { genre_id: genre.genre_id },
      genre,
      { upsert: true, returnDocument: "after" }
    )
  }

  console.log(`[recommendation-service] Seeded ${TMDB_GENRES.length} genres`)
}

/**
 * Main seed function
 */
const seed = async () => {
  try {
    const uriCandidates = [
      process.env.MONGO_URI,
      process.env.MONGO_URI_FALLBACK
    ].filter(Boolean)

    if (uriCandidates.length === 0) {
      throw new Error("MONGO_URI or MONGO_URI_FALLBACK environment variable is required")
    }

    let connected = false
    for (const mongoUri of uriCandidates) {
      try {
        console.log("[recommendation-service] Connecting to MongoDB...")
        await mongoose.connect(mongoUri, {
          serverSelectionTimeoutMS: 10000
        })
        console.log("[recommendation-service] Connected to MongoDB")
        connected = true
        break
      } catch (error) {
        console.warn(`[recommendation-service] Connection failed: ${error.message}`)
        if (mongoUri !== uriCandidates[uriCandidates.length - 1]) {
          console.log("[recommendation-service] Trying fallback URI...")
        }
      }
    }

    if (!connected) {
      throw new Error("Could not connect to any MongoDB instance")
    }

    await seedGenres()

    console.log("\n[recommendation-service] Database seeding completed successfully!")
    console.log("[recommendation-service] Note: Movies are fetched live from TMDB — no local movie seeding needed.")
  } catch (error) {
    console.error("[recommendation-service] Seeding failed:", error)
    process.exit(1)
  } finally {
    await mongoose.disconnect()
    console.log("[recommendation-service] Disconnected from MongoDB")
  }
}

if (require.main === module) {
  seed()
}

module.exports = { seed, seedGenres, TMDB_GENRES }
