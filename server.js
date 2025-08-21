const express = require("express");
const fs = require("fs");
const app = express();
const PORT = 3000;

let data = [];

// Read the "stream.json" periodically (simulate real-time)
setInterval(() => {
  try {
    const raw = fs.readFileSync("stream.json");
    data = JSON.parse(raw);
  } catch (err) {
    console.log("Waiting for data...");
  }
}, 100);

// Serve latest data
app.get("/data", (req, res) => {
  res.json(data);
});

app.use(express.static(__dirname + "/public"));

app.listen(PORT, () => console.log(`Server running on http://localhost:${PORT}`));
