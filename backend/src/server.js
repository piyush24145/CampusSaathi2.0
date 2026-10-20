const express = require("express");
const cors = require("cors");
require("dotenv").config();

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json());

app.get("/", (req, res) => {
    res.json({
        success: true,
        message: "Welcome to CampusSathi AI Backend!"
    });
});

app.get("/api/health", (req, res) => {
    res.json({
        success: true,
        service: "CampusSathi Backend",
        status: "running"
    });
});

app.listen(PORT, () => {
    console.log(`Backend running at http://localhost:${PORT}`);
});