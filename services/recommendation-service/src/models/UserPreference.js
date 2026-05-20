const mongoose = require("mongoose")


const userPreferenceSchema = new mongoose.Schema({
  user_id: {
    type: mongoose.Schema.Types.ObjectId,
    required: true,
    index: true
  },
  genre_id: {
    type: Number,
    required: true,
    index: true
  },
  score: {
    type: Number,
    required: true,
    default: 1.0,
    min: 0,
    max: 10
  }
}, { timestamps: true })

userPreferenceSchema.index({ user_id: 1, genre_id: 1 }, { unique: true })

module.exports = mongoose.model("UserPreference", userPreferenceSchema)
