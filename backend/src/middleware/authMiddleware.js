const jwt = require("jsonwebtoken")

const authMiddleware = (req, res, next) => {
  const authHeader = req.headers.authorization || ""
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : null

  if (!token) {
    return res.status(401).json({ message: "Authentication token is missing." })
  }

  const primarySecret = process.env.JWT_SECRET || "cinescope-jwt-secret"
  const fallbackSecret = "cinescope-jwt-secret"
  const secretsToTry = primarySecret === fallbackSecret
    ? [primarySecret]
    : [primarySecret, fallbackSecret]

  for (const secret of secretsToTry) {
    try {
      const payload = jwt.verify(token, secret)
      req.auth = payload
      return next()
    } catch (error) {
      continue
    }
  }

  return res.status(401).json({ message: "Invalid or expired token." })
}

module.exports = authMiddleware
