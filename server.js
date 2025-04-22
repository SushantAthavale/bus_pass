// server.js
const express = require('express');
const bodyParser = require('body-parser');
const sqlite3 = require('sqlite3').verbose();
const bcrypt = require('bcrypt');
const cors = require('cors');

const app = express();
const db = new sqlite3.Database('bus_pass.db');

app.use(cors()); // Enable CORS for all routes
app.use(bodyParser.json());

app.post('/login', (req, res) => {
    const { email, password } = req.body;

    // Query the database for the user
    db.get('SELECT * FROM bus_passes WHERE email = ?', [email], (err, row) => {
        if (err) {
            return res.status(500).json({ success: false, message: 'Database error' });
        }
        if (row) {
            // Compare the hashed password
            bcrypt.compare(password, row.password, (err, isMatch) => {
                if (err) {
                    return res.status(500).json({ success: false, message: 'Error comparing passwords' });
                }
                if (isMatch) {
                    return res.json({ success: true });
                } else {
                    return res.json({ success: false });
                }
            });
        } else {
            return res.json({ success: false });
        }
    });
});

app.listen(3000, () => {
    console.log('Server is running on port 3000');
});