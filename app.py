from flask import Flask, request, redirect, url_for, render_template
import sqlite3

app = Flask(__name__)

# Initialize the SQLite database
def init_db():
    conn = sqlite3.connect('bus_pass.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            age INTEGER NOT NULL,
            validity_days INTEGER NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    name = request.form['name']
    email = request.form['email']
    age = request.form['age']
    validity_days = request.form['days']

    conn = sqlite3.connect('bus_pass.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO registrations (name, email, age, validity_days)
        VALUES (?, ?, ?, ?)
    ''', (name, email, age, validity_days))
    conn.commit()
    conn.close()

    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
