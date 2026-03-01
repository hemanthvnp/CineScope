const express = require("express")
const userController = require("../controllers/userController")
const authMiddleware = require("../middleware/authMiddleware")

const router = express.Router()

router.post("/register/initiate", userController.initiateRegistration)
router.post("/register/verify", userController.verifyRegistrationOtp)
router.post("/login", userController.loginUser)
router.get("/me", authMiddleware, userController.getProfile)

module.exports = router
