const mongoose = require("mongoose")

const userSchema = new mongoose.Schema({
  name: { type: String, required: true, trim: true },
  screenName: { type: String, trim: true, default: "" },
  email: { type: String, required: true, unique: true, lowercase: true, trim: true },
  password: { type: String, required: true },
  favoriteGenre: { type: String, default: "" },
  favoriteEra: { type: String, default: "" },
  preferredLanguage: { type: String, default: "" },
  signatureLine: { type: String, default: "" },
  emailVerified: { type: Boolean, default: false },
  preferencePriorities: {
    language: { type: Number, default: 2 }, // 1=Low, 2=Normal, 3=High
    genre: { type: Number, default: 2 },
    era: { type: Number, default: 2 }
  }
}, { timestamps: true })

module.exports = mongoose.model("User", userSchema)