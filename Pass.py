import sqlite3
import qrcode
import os
import datetime
import cv2
import random
import hashlib
import base64
import secrets
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session, jsonify, Response
from werkzeug.security import generate_password_hash
from functools import wraps

app = Flask(__name__, static_folder='static')
app.secret_key = 'your-secret-key-here'  # Required for flash messages

# Create necessary directories if they don't exist
os.makedirs('static/user_images', exist_ok=True)
os.makedirs('static/qr_codes', exist_ok=True)

def get_db_connection():
    """Get a database connection with proper error handling."""
    try:
        print("Attempting to connect to database...")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Database file exists: {os.path.exists('bus_pass.db')}")
        
        # Ensure the database file exists
        if not os.path.exists('bus_pass.db'):
            print("Database file not found. Initializing new database...")
            init_db()
        
        # Try to connect to the database
        conn = sqlite3.connect('bus_pass.db', check_same_thread=False)
        conn.row_factory = sqlite3.Row
        print("Database connection established successfully")
        return conn
        
    except sqlite3.Error as e:
        print(f"Database connection error: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error args: {e.args}")
        raise
        
    except Exception as e:
        print(f"Unexpected error while connecting to database: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error args: {e.args}")
        raise

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create bus_passes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bus_passes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            age INTEGER NOT NULL,
            pass_number TEXT NOT NULL UNIQUE,
            valid_until DATE NOT NULL,
            mobile_no TEXT NOT NULL,
            district TEXT NOT NULL,
            photo_data TEXT,
            qr_code TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Check if is_admin column exists
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'is_admin' not in columns:
        cursor.execute('ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0')
        conn.commit()
    
    # Create user_activity table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            action TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create settings table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            passValidity INTEGER DEFAULT 6,
            maxPassesPerUser INTEGER DEFAULT 1,
            notificationDays INTEGER DEFAULT 7,
            smtpServer TEXT,
            smtpPort INTEGER DEFAULT 587,
            smtpUsername TEXT,
            smtpPassword TEXT,
            fromEmail TEXT,
            backupFrequency TEXT DEFAULT 'daily',
            backupLocation TEXT DEFAULT 'backups',
            retentionPeriod INTEGER DEFAULT 30
        )
    ''')
    
    conn.commit()
    conn.close()

def hash_password(password):
    """Hashes the password for secure storage."""
    return hashlib.sha256(password.encode()).hexdigest()

def generate_pass_number():
    """Generates a unique pass number."""
    return f"BP-{random.randint(100000, 999999)}"

def generate_qr_code(pass_number):
    """Generates a QR code for the pass number."""
    try:
        # Create QR code data
        qr_data = f"Pass Number: {pass_number}"

        # Create QR code image
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # Generate QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code
        qr_code = f"static/qr_codes/qr_code_{pass_number}.png"
        os.makedirs(os.path.dirname(qr_code), exist_ok=True)
        img.save(qr_code)
        
        print(f"QR code generated and saved at: {qr_code}")
        return qr_code
    except Exception as e:
        print(f"Error generating QR code: {e}")
        return None

def save_base64_image(base64_data, pass_number):
    """Saves a base64 encoded image to a file."""
    try:
        # Remove the data URL prefix if present
        if ',' in base64_data:
            base64_data = base64_data.split(',')[1]
        
        # Decode base64 data
        image_data = base64.b64decode(base64_data)
        
        # Create the image path
        image_path = f"static/user_images/user_image_{pass_number}.jpg"
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        
        # Save the image
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        return image_path
    except Exception as e:
        print(f"Error saving image: {e}")
        return None

# def generate_otp():
#     """Generates a 6-digit OTP."""
#     return str(random.randint(100000, 999999))

# def verify_otp(email, mobile, otp):
#     """Verify the OTP entered by the user."""
#     conn = None
#     try:
#         conn = get_db_connection()
#         cursor = conn.cursor()
        
#         # Get the most recent OTP for the user (within last 5 minutes)
#         cursor.execute('''
#             SELECT otp FROM otp_verification 
#             WHERE email = ? AND mobile = ? 
#             AND created_at >= datetime('now', '-5 minutes')
#             ORDER BY created_at DESC LIMIT 1
#         ''', (email, mobile))
        
#         result = cursor.fetchone()
        
#         if result and str(result[0]) == str(otp):
#             # Delete the used OTP
#             cursor.execute('''
#                 DELETE FROM otp_verification 
#                 WHERE email = ? AND mobile = ? AND otp = ?
#             ''', (email, mobile, otp))
            
#             conn.commit()
#             return True
            
#         return False
        
#     except Exception as e:
#         print(f"Error verifying OTP: {str(e)}")
#         if conn:
#             conn.rollback()
#         return False
        
#     finally:
#         if conn:
#             conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            user = cursor.fetchone()
            
            if user and user['password'] == password:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['is_admin'] = user['is_admin']
                
                # Log the login
                log_user_activity(user['id'], username, 'User login')
                
                fun_messages = [
                    "Welcome back! Ready to ride the bus wave? 🚌",
                    "Hey there! Your bus pass adventure continues! 🎉",
                    "Welcome aboard! Let's make some bus memories! 🌟",
                    "Great to see you! Time to hop on the bus express! 🚀",
                    "You're back! The bus misses you! 🚌💨"
                ]
                flash(random.choice(fun_messages), 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password', 'error')
        except Exception as e:
            flash('An error occurred during login', 'error')
        finally:
            conn.close()
    
    return render_template('login.html')

@app.route('/register_user', methods=['GET', 'POST'])
def register_user():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        is_admin = request.form.get('is_admin', 0)  # Default to 0 (not admin)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO users (username, password, email, is_admin)
                VALUES (?, ?, ?, ?)
            ''', (username, password, email, is_admin))
            
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            
            # Log the registration
            log_user_activity(cursor.lastrowid, username, 'User registration')
            
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists!', 'error')
        finally:
            conn.close()
    
    return render_template('register_user.html')

@app.route('/logout')
def logout():
    username = session.get('username', 'friend')
    session.clear()
    fun_messages = [
        f"Bye {username}! Don't forget to wave at the bus! 👋",
        f"See you later {username}! The bus will miss you! 🚌",
        f"Take care {username}! Come back soon for more bus adventures! 🌟",
        f"Farewell {username}! Your bus pass will be waiting! 🎫",
        f"Until next time {username}! Keep riding the bus wave! 🌊"
    ]
    flash(random.choice(fun_messages), 'info')
    return redirect(url_for('index'))

# Add login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if request.method == 'POST':
        conn = None
        try:
            # Get form data
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            age = request.form.get('age', '').strip()
            days = request.form.get('days', '').strip()
            mobile = request.form.get('mobile', '').strip()
            district = request.form.get('district', '').strip()
            photo_data = request.form.get('photo_data', '').strip()
            
            print(f"Received photo data length: {len(photo_data)}")  # Debug log
            
            # Validate required fields
            if not all([name, email, age, days, mobile, district, photo_data]):
                return 'All fields are required', 400
            
            # Validate data types
            try:
                age = int(age)
                days = int(days)
                mobile = str(mobile)  # Convert to string to handle leading zeros
            except ValueError:
                return 'Invalid data format for age, days, or mobile number', 400
            
            # Generate pass number
            pass_number = generate_pass_number()
            
            # Generate QR code
            qr_code = generate_qr_code(pass_number)
            if not qr_code:
                return 'Error generating QR code', 500
            
            # Calculate valid until date
            valid_until = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Store user data
            conn = get_db_connection()
            cursor = conn.cursor()
            
            try:
                # Check if pass number already exists
                cursor.execute('SELECT pass_number FROM bus_passes WHERE pass_number = ?', (pass_number,))
                if cursor.fetchone():
                    return 'Pass number already exists. Please try again.', 400
                
                # Insert new pass
                cursor.execute('''
                    INSERT INTO bus_passes (
                        name, email, age, pass_number, valid_until,
                        mobile_no, district, photo_data, qr_code
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    name, email, age, pass_number, valid_until,
                    mobile, district, photo_data, qr_code
                ))
                
                conn.commit()
                print(f"Successfully stored pass data for {pass_number}")  # Debug log
                
                # Log the pass registration
                log_user_activity(session['user_id'], session['username'], 
                                 f'Registered new pass: {pass_number}')
                
                # Redirect to success page with all necessary parameters
                return redirect(url_for('registration_success',
                                     pass_number=pass_number,
                                     name=name,
                                     email=email,
                                     mobile=mobile,
                                     valid_until=valid_until))
                
            except sqlite3.Error as e:
                print(f"Database error: {e}")
                if conn:
                    conn.rollback()
                return f'Database error: {str(e)}', 500
                
        except Exception as e:
            print(f"Error in registration: {str(e)}")
            if conn:
                conn.rollback()
            return f'Registration error: {str(e)}', 500

        finally:
            if conn:
                conn.close()

    # Handle GET request for registration page
    return render_template('register.html')

@app.route('/registration_success')
def registration_success():
    # Get parameters from URL
    pass_number = request.args.get('pass_number')
    name = request.args.get('name')
    email = request.args.get('email')
    mobile = request.args.get('mobile')
    valid_until = request.args.get('valid_until')
    
    # Validate required parameters
    if not all([pass_number, name, email, mobile, valid_until]):
        flash('Missing required parameters', 'error')
        return redirect(url_for('register'))
    
    return render_template('registration_success.html',
                         pass_number=pass_number,
                         name=name,
                         email=email,
                         mobile=mobile,
                         valid_until=valid_until)

# @app.route('/generate_otp', methods=['GET'])
# def generate_otp_route():
#     """Generate and store OTP for verification"""
#     try:
#         email = request.args.get('email')
#         mobile = request.args.get('mobile')
        
#         # Validate inputs
#         if not email or not mobile:
#             return jsonify({
#                 'success': False,
#                 'error': 'Email and mobile number are required'
#             }), 400
            
#         if not email.strip() or not mobile.strip():
#             return jsonify({
#                 'success': False,
#                 'error': 'Email and mobile number cannot be empty'
#             }), 400
            
#         # Generate OTP
#         otp = generate_otp()
        
#         # Store OTP in database
#         conn = None
#         try:
#             conn = get_db_connection()
#             cursor = conn.cursor()
            
#             # Create OTP verification table if it doesn't exist
#             cursor.execute('''
#                 CREATE TABLE IF NOT EXISTS otp_verification (
#                     id INTEGER PRIMARY KEY AUTOINCREMENT,
#                     email TEXT NOT NULL,
#                     mobile TEXT NOT NULL,
#                     otp TEXT NOT NULL,
#                     created_at DATETIME DEFAULT CURRENT_TIMESTAMP
#                 )
#             ''')
            
#             # Clean up old OTPs (older than 5 minutes)
#             cursor.execute('''
#                 DELETE FROM otp_verification 
#                 WHERE created_at < datetime('now', '-5 minutes')
#             ''')
            
#             # Insert new OTP
#             cursor.execute('''
#                 INSERT INTO otp_verification (email, mobile, otp)
#                 VALUES (?, ?, ?)
#             ''', (email, mobile, otp))
            
#             conn.commit()
            
#             # In a real application, you would send the OTP via email or SMS
#             # For now, we'll just return it for testing
#             return jsonify({
#                 'success': True,
#                 'message': 'OTP sent successfully',
#                 'otp': otp,  # Remove this in production
#                 'expiry': '5 minutes'
#             })
            
#         except sqlite3.Error as e:
#             print(f"Database error: {e}")
#             if conn:
#                 conn.rollback()
#             return jsonify({
#                 'success': False,
#                 'error': 'Database error occurred. Please try again.'
#             }), 500
            
#         finally:
#             if conn:
#                 conn.close()
            
#     except Exception as e:
#         print(f"Error generating OTP: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': 'An error occurred while generating OTP. Please try again.'
#         }), 500

@app.route('/scan_qr', methods=['POST'])
def scan_qr():
    """Scans a QR code using the webcam and retrieves pass details."""
    cap = cv2.VideoCapture(0)  # Access the default webcam
    detector = cv2.QRCodeDetector()

    if not cap.isOpened():
        return "Cannot access the webcam. Please try again.", 500

    pass_number = None
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Detect and decode the QR code
        data, bbox, _ = detector.detectAndDecode(frame)
        if data:
            print(f"QR Code Data: {data}")  # Debug log
            try:
                # Extract pass number from QR code data
                if "Pass Number: " in data:
                    pass_number = data.split("Pass Number: ")[1].split(",")[0].strip()
                    print(f"Extracted Pass Number: {pass_number}")  # Debug log
                    
                    # Get pass details from database
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM bus_passes WHERE pass_number = ?", (pass_number,))
                    pass_data = cursor.fetchone()
                    conn.close()
                    
                    if pass_data:
                        # Format the pass details
                        pass_details = f"Pass Number: {pass_data['pass_number']}\n"
                        pass_details += f"Name: {pass_data['name']}\n"
                        pass_details += f"Valid Until: {pass_data['valid_until']}"
                        
                        # Release the webcam
                        cap.release()
                        cv2.destroyAllWindows()
                        
                        fun_messages = [
                            "QR Code scanned successfully! 🎯",
                            "Got it! Your pass details are ready! ✅",
                            "Scan complete! Time to check your pass! 🔍",
                            "Perfect scan! Here's your pass info! ✨",
                            "QR Code detected! Let's see your pass! 🚌"
                        ]
                        flash(random.choice(fun_messages), 'success')
                        return pass_details
                    else:
                        print(f"Pass number {pass_number} not found in database")  # Debug log
                        pass_number = None
                else:
                    print("Unexpected QR code format")  # Debug log
            except Exception as e:
                print(f"Error processing QR code data: {e}")  # Debug log
                pass_number = None

        # Display the webcam feed
        cv2.imshow("Scan QR Code - Press 'q' to quit", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

    fun_messages = [
        "Oops! No QR code detected. Try again! 🔄",
        "Let's try scanning that QR code again! 📱",
        "No QR code found. Make sure it's in view! 👀",
        "Scan failed. Let's give it another shot! 🎯",
        "Couldn't read the QR code. Try repositioning! 🔄"
    ]
    flash(random.choice(fun_messages), 'error')
    return "No valid QR code detected or pass not found. Please try again.", 400

@app.route('/display', methods=['GET', 'POST'])
def display_pass():
    if request.method == 'GET':
        pass_number = request.args.get('pass_number', '').strip()
    else:
        pass_number = request.form.get('pass_number', '').strip()

    print(f"Displaying pass for pass_number: {pass_number}")  # Debug log

    if not pass_number:
        return "Pass number is required", 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Debug: Print the SQL query
        query = "SELECT * FROM bus_passes WHERE pass_number = ?"
        print(f"Executing query: {query} with pass_number: {pass_number}")
        
        cursor.execute(query, (pass_number,))
        result = cursor.fetchone()

        if result:
            # Convert result to dictionary for easier access
            pass_data = dict(result)
            print(f"Retrieved pass data: {pass_data}")  # Debug log
            
            # Convert valid_until string to date object
            if pass_data['valid_until']:
                pass_data['valid_until'] = datetime.datetime.strptime(pass_data['valid_until'], '%Y-%m-%d').date()
            
            # Handle photo data
            image_path = None
            if pass_data['photo_data']:
                if pass_data['photo_data'].startswith('data:image'):
                    image_path = pass_data['photo_data']
                else:
                    if not pass_data['photo_data'].startswith('static/'):
                        image_path = f"static/{pass_data['photo_data']}"
                    else:
                        image_path = pass_data['photo_data']
            
            # Ensure QR code path is relative to static folder
            if pass_data['qr_code'] and not pass_data['qr_code'].startswith('static/'):
                pass_data['qr_code'] = f"static/{pass_data['qr_code']}"
            
            return render_template('display.html',
                                name=pass_data['name'],
                                email=pass_data['email'],
                                age=pass_data['age'],
                                pass_number=pass_data['pass_number'],
                                valid_until=pass_data['valid_until'],
                                mobile=pass_data['mobile_no'],
                                district=pass_data['district'],
                                image_path=image_path,
                                qr_code=pass_data['qr_code'],
                                today=datetime.date.today())
        else:   
            print(f"Pass not found for pass_number: {pass_number}")  # Debug log
            return "Pass not found", 404
            
    except Exception as e:
        print(f"Error displaying pass: {str(e)}")  # Debug log
        return f"Error displaying pass: {str(e)}", 500
        
    finally:
        if conn:
            conn.close()
@app.route('/renew/<pass_number>', methods=['GET', 'POST'])
def renew_pass(pass_number):
    if request.method == 'POST':
        conn = None
        try:
            # Get and validate days
            days = request.form.get('days')
            print(f"Received days: {days}")  # Debug log
            
            if not days:
                flash("Please select a valid duration", "error")
                return redirect(url_for('renew_pass', pass_number=pass_number))
            
            try:
                days = int(days)
                if days <= 0:
                    flash("Please select a valid duration", "error")
                    return redirect(url_for('renew_pass', pass_number=pass_number))
            except ValueError:
                flash("Invalid duration format", "error")
                return redirect(url_for('renew_pass', pass_number=pass_number))
            
            # Get database connection
            conn = get_db_connection()
            cursor = conn.cursor()
            
            try:
                # First verify the pass exists
                cursor.execute("SELECT valid_until FROM bus_passes WHERE pass_number = ?", (pass_number,))
                result = cursor.fetchone()
                
                if not result:
                    flash("Pass not found", "error")
                    return redirect(url_for('index'))
                
                print(f"Current pass details: {result}")  # Debug log
                
                # Get current valid_until date
                current_valid_until = datetime.datetime.strptime(result['valid_until'], '%Y-%m-%d').date()
                current_date = datetime.date.today()
                
                print(f"Current valid until: {current_valid_until}")  # Debug log
                print(f"Current date: {current_date}")  # Debug log
                
                # Calculate new valid_until date
                if current_date > current_valid_until:
                    new_valid_until = current_date + datetime.timedelta(days=days)
                else:
                    new_valid_until = current_valid_until + datetime.timedelta(days=days)
                
                print(f"New valid until: {new_valid_until}")  # Debug log
                
                # Update the valid_until date
                update_query = "UPDATE bus_passes SET valid_until = ? WHERE pass_number = ?"
                update_params = (new_valid_until.strftime('%Y-%m-%d'), pass_number)
                
                print(f"Executing update query: {update_query}")  # Debug log
                print(f"With parameters: {update_params}")  # Debug log
                
                # Execute the update
                cursor.execute(update_query, update_params)
                
                # Verify the update
                cursor.execute("SELECT valid_until FROM bus_passes WHERE pass_number = ?", (pass_number,))
                updated_result = cursor.fetchone()
                
                if updated_result and updated_result['valid_until'] == new_valid_until.strftime('%Y-%m-%d'):
                    # Commit the transaction
                    conn.commit()
                    print("Update successful, changes committed")  # Debug log
                    flash("Pass renewed successfully!", "success")
                    
                    # Log the pass renewal
                    log_user_activity(session['user_id'], session['username'], 
                                     f'Renewed pass: {pass_number}')
                    
                    return redirect(url_for('view_pass', pass_number=pass_number))
                else:
                    # Rollback if verification failed
                    conn.rollback()
                    print("Update verification failed")  # Debug log
                    flash("Failed to update pass validity", "error")
                    return redirect(url_for('renew_pass', pass_number=pass_number))
                
            except sqlite3.Error as e:
                print(f"Database error during update: {str(e)}")
                print(f"Error type: {type(e)}")
                print(f"Error args: {e.args}")
                if conn:
                    conn.rollback()
                flash("Database error occurred. Please try again.", "error")
                return redirect(url_for('renew_pass', pass_number=pass_number))
                
            except ValueError as e:
                print(f"Error processing dates: {str(e)}")
                if conn:
                    conn.rollback()
                flash("Error processing pass dates. Please contact support.", "error")
                return redirect(url_for('renew_pass', pass_number=pass_number))
                
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            print(f"Error type: {type(e)}")
            print(f"Error args: {e.args}")
            if conn:
                conn.rollback()
            flash("An unexpected error occurred. Please try again.", "error")
            return redirect(url_for('renew_pass', pass_number=pass_number))
            
        finally:
            if conn:
                try:
                    conn.close()
                    print("Database connection closed successfully")
                except Exception as e:
                    print(f"Error closing database connection: {e}")
    
    # GET request - display renewal form
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Verify the pass exists
        cursor.execute("SELECT valid_until FROM bus_passes WHERE pass_number = ?", (pass_number,))
        result = cursor.fetchone()
        
        if not result:
            flash("Pass not found", "error")
            return redirect(url_for('index'))
            
        return render_template('renew.html', pass_number=pass_number)
        
    except Exception as e:
        print(f"Error loading renewal page: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error args: {e.args}")
        flash("Error loading renewal page. Please try again.", "error")
        return redirect(url_for('index'))
        
    finally:
        if conn:
            try:
                conn.close()
                print("Database connection closed successfully")
            except Exception as e:
                print(f"Error closing database connection: {e}")

@app.route('/scan_qr_page')
def scan_qr_page():
    """Renders the QR scanning page."""
    return render_template('scan_qr.html')

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

@app.route('/debug/db')
def debug_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get table info
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        # Get bus_passes data
        cursor.execute("SELECT * FROM bus_passes")
        passes = cursor.fetchall()
        
        conn.close()
        
        # Format response as plain text
        response = "Tables in database:\n"
        for table in tables:
            response += f"- {table['name']}\n"
        
        response += "\nBus passes data:\n"
        for pass_data in passes:
            response += f"\nPass Number: {pass_data['pass_number']}\n"
            response += f"Name: {pass_data['name']}\n"
            response += f"Email: {pass_data['email']}\n"
            response += f"Age: {pass_data['age']}\n"
            response += f"Valid Until: {pass_data['valid_until']}\n"
            response += f"Mobile: {pass_data['mobile_no']}\n"
            response += f"District: {pass_data['district']}\n"
            response += "-" * 50 + "\n"
        
        return response, 200
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/view_pass', methods=['GET', 'POST'])
@login_required
def view_pass():
    """Handle viewing pass details."""
    if request.method == 'POST':
        pass_number = request.form.get('pass_number')
    else:
        pass_number = request.args.get('pass_number')
    
    print(f"Received pass number: {pass_number}")  # Debug log
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get recent pass numbers
        cursor.execute('''
            SELECT pass_number, name 
            FROM bus_passes 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        recent_passes = cursor.fetchall()
        
        # Initialize pass_details as None
        pass_details = None
        
        if pass_number:
            # Debug: Print the SQL query
            query = "SELECT * FROM bus_passes WHERE pass_number = ?"
            print(f"Executing query: {query} with pass_number: {pass_number}")
            
            # Get pass details
            cursor.execute(query, (pass_number,))
            pass_data = cursor.fetchone()
            
            if pass_data:
                print(f"Retrieved pass data: {pass_data}")  # Debug log
                
                # Convert to dictionary for easier access
                pass_data = dict(pass_data)
                print(f"Converted pass data to dict: {pass_data}")  # Debug log
                
                # Handle photo data
                photo_data = None
                if pass_data.get('photo_data'):
                    if pass_data['photo_data'].startswith('data:image'):
                        photo_data = pass_data['photo_data']
                    else:
                        if not pass_data['photo_data'].startswith('static/'):
                            photo_data = f"static/{pass_data['photo_data']}"
                        else:
                            photo_data = pass_data['photo_data']
                
                # Handle QR code data
                qr_code = None
                if pass_data.get('qr_code'):
                    if not pass_data['qr_code'].startswith('static/'):
                        qr_code = f"static/{pass_data['qr_code']}"
                    else:
                        qr_code = pass_data['qr_code']
                
                # Check if pass is active
                valid_until = datetime.datetime.strptime(pass_data['valid_until'], '%Y-%m-%d').date()
                today = datetime.date.today()
                status = 'Active' if valid_until >= today else 'Expired'
                
                # Prepare pass details with safe dictionary access
                pass_details = {
                    'pass_number': pass_data.get('pass_number', ''),
                    'name': pass_data.get('name', ''),
                    'valid_from': pass_data.get('valid_from', 'Not specified'),
                    'valid_until': pass_data.get('valid_until', ''),
                    'status': status,
                    'photo_data': photo_data,
                    'qr_code': qr_code
                }
            else:
                print(f"Pass not found for pass_number: {pass_number}")  # Debug log
                flash('Pass not found', 'error')
        
        print(f"Rendering template with pass_details: {pass_details}")  # Debug log
        
        return render_template('view_pass.html', 
                            pass_details=pass_details,
                            recent_passes=recent_passes)
        
    except Exception as e:
        print(f"Error viewing pass: {str(e)}")  # Debug log
        print(f"Error type: {type(e)}")  # Debug log
        print(f"Error args: {e.args}")  # Debug log
        flash('An error occurred while viewing the pass', 'error')
        return render_template('view_pass.html', 
                            pass_details=None,
                            recent_passes=[])
    finally:
        if conn:
            conn.close()

@app.route('/renew', methods=['GET'])
@login_required
def renew():
    """Render the renew pass search page."""
    return render_template('renew.html')

# Admin routes
@app.route('/admin')
@login_required
def admin_dashboard():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not user['is_admin']:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    return render_template('admin.html')

@app.route('/admin/users')
@login_required
def admin_users():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not user['is_admin']:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    return render_template('admin_users.html')

@app.route('/admin/users/data')
@login_required
def admin_users_data():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    # Get all users
    cursor.execute('SELECT id, username, email, is_admin, created_at FROM users')
    users = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(user) for user in users])

@app.route('/admin/passes')
@login_required
def admin_passes():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not user['is_admin']:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    return render_template('admin_passes.html')

@app.route('/admin/passes/data')
@login_required
def admin_passes_data():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    # Get filter parameters
    status = request.args.get('status', '')
    district = request.args.get('district', '')
    search = request.args.get('search', '')
    
    # Build query
    query = '''
        SELECT pass_number, name, email, district, valid_until,
               CASE 
                   WHEN valid_until >= date('now') THEN 'Active'
                   ELSE 'Expired'
               END as status
        FROM bus_passes
        WHERE 1=1
    '''
    params = []
    
    if status:
        if status == 'active':
            query += ' AND valid_until >= date("now")'
        else:
            query += ' AND valid_until < date("now")'
    
    if district:
        query += ' AND district = ?'
        params.append(district)
    
    if search:
        query += ' AND (pass_number LIKE ? OR name LIKE ? OR email LIKE ?)'
        search_param = f'%{search}%'
        params.extend([search_param, search_param, search_param])
    
    query += ' ORDER BY created_at DESC'
    
    cursor.execute(query, params)
    passes = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(pass_data) for pass_data in passes])

@app.route('/admin/districts')
@login_required
def admin_districts():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    # Get unique districts
    cursor.execute('SELECT DISTINCT district FROM bus_passes ORDER BY district')
    districts = [row['district'] for row in cursor.fetchall()]
    conn.close()
    
    return jsonify(districts)

@app.route('/admin/passes/export')
@login_required
def admin_export_passes():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    # Get filter parameters
    status = request.args.get('status', '')
    district = request.args.get('district', '')
    
    # Build query
    query = '''
        SELECT pass_number, name, email, district, valid_until,
               CASE 
                   WHEN valid_until >= date('now') THEN 'Active'
                   ELSE 'Expired'
               END as status
        FROM bus_passes
        WHERE 1=1
    '''
    params = []
    
    if status:
        if status == 'active':
            query += ' AND valid_until >= date("now")'
        else:
            query += ' AND valid_until < date("now")'
    
    if district:
        query += ' AND district = ?'
        params.append(district)
    
    cursor.execute(query, params)
    passes = cursor.fetchall()
    conn.close()
    
    # Create CSV content
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Pass Number', 'Name', 'Email', 'District', 'Valid Until', 'Status'])
    
    # Write data
    for pass_data in passes:
        writer.writerow([
            pass_data['pass_number'],
            pass_data['name'],
            pass_data['email'],
            pass_data['district'],
            pass_data['valid_until'],
            pass_data['status']
        ])
    
    output.seek(0)
    
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=bus_passes.csv'}
    )

@app.route('/admin/reports')
@login_required
def admin_reports():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not user['is_admin']:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    return render_template('admin_reports.html')

@app.route('/admin/settings')
@login_required
def admin_settings():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not user['is_admin']:
        flash('Access denied. Admin privileges required.', 'error')
        return redirect(url_for('index'))
    
    return render_template('admin_settings.html')

# Settings routes
@app.route('/admin/settings/get')
@login_required
def get_settings():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    # Get settings from database
    cursor.execute('SELECT * FROM settings')
    settings = cursor.fetchone()
    conn.close()
    
    if not settings:
        return jsonify({
            'passValidity': 6,
            'maxPassesPerUser': 1,
            'notificationDays': 7,
            'smtpServer': '',
            'smtpPort': 587,
            'smtpUsername': '',
            'smtpPassword': '',
            'fromEmail': '',
            'backupFrequency': 'daily',
            'backupLocation': '',
            'retentionPeriod': 30
        })
    
    return jsonify(dict(settings))

@app.route('/admin/settings/system', methods=['POST'])
@login_required
def save_system_settings():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        data = request.get_json()
        
        # Update or insert system settings
        cursor.execute('''
            INSERT OR REPLACE INTO settings (
                passValidity, maxPassesPerUser, notificationDays
            ) VALUES (?, ?, ?)
        ''', (
            data.get('passValidity', 6),
            data.get('maxPassesPerUser', 1),
            data.get('notificationDays', 7)
        ))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'System settings saved successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/admin/settings/email', methods=['POST'])
@login_required
def save_email_settings():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        data = request.get_json()
        
        # Update or insert email settings
        cursor.execute('''
            INSERT OR REPLACE INTO settings (
                fromEmail, smtpPassword
            ) VALUES (?, ?)
        ''', (
            data.get('fromEmail', ''),
            data.get('smtpPassword', '')
        ))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Email settings saved successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/admin/settings/backup', methods=['POST'])
@login_required
def save_backup_settings():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        data = request.get_json()
        
        # Update or insert backup settings
        cursor.execute('''
            INSERT OR REPLACE INTO settings (
                backupFrequency, backupLocation, retentionPeriod
            ) VALUES (?, ?, ?)
        ''', (
            data.get('backupFrequency', 'daily'),
            data.get('backupLocation', ''),
            data.get('retentionPeriod', 30)
        ))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Backup settings saved successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/admin/settings/backup/create', methods=['POST'])
@login_required
def create_backup():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Get backup location from settings
        cursor.execute('SELECT backupLocation FROM settings')
        settings = cursor.fetchone()
        backup_location = settings['backupLocation'] if settings else 'backups'
        
        # Create backup directory if it doesn't exist
        import os
        if not os.path.exists(backup_location):
            os.makedirs(backup_location)
        
        # Create backup filename with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(backup_location, f'backup_{timestamp}.db')
        
        # Copy database file
        import shutil
        shutil.copy2('bus_pass.db', backup_file)
        
        return jsonify({'success': True, 'message': 'Backup created successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/admin/settings/backup/restore', methods=['POST'])
@login_required
def restore_backup():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Get backup location from settings
        cursor.execute('SELECT backupLocation FROM settings')
        settings = cursor.fetchone()
        backup_location = settings['backupLocation'] if settings else 'backups'
        
        # Get list of backup files
        import os
        backup_files = [f for f in os.listdir(backup_location) if f.startswith('backup_') and f.endswith('.db')]
        if not backup_files:
            return jsonify({'success': False, 'message': 'No backup files found'})
        
        # Get the most recent backup
        backup_files.sort(reverse=True)
        latest_backup = os.path.join(backup_location, backup_files[0])
        
        # Restore database
        import shutil
        shutil.copy2(latest_backup, 'bus_pass.db')
        
        return jsonify({'success': True, 'message': 'Backup restored successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

# Function to log user activity
def log_user_activity(user_id, username, action):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO user_activity (user_id, username, action)
        VALUES (?, ?, ?)
    ''', (user_id, username, action))
    
    conn.commit()
    conn.close()

@app.route('/admin/stats')
@login_required
def admin_stats():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    # Get total passes
    cursor.execute('SELECT COUNT(*) FROM bus_passes')
    total_passes = cursor.fetchone()[0]
    
    # Get active passes
    cursor.execute('SELECT COUNT(*) FROM bus_passes WHERE valid_until >= date("now")')
    active_passes = cursor.fetchone()[0]
    
    # Get expired passes
    cursor.execute('SELECT COUNT(*) FROM bus_passes WHERE valid_until < date("now")')
    expired_passes = cursor.fetchone()[0]
    
    # Get total users
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        'total_passes': total_passes,
        'active_passes': active_passes,
        'expired_passes': expired_passes,
        'total_users': total_users
    })

@app.route('/admin/recent_passes')
@login_required
def admin_recent_passes():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    # Get recent passes
    cursor.execute('''
        SELECT pass_number, name, created_at,
               CASE 
                   WHEN valid_until >= date('now') THEN 'Active'
                   ELSE 'Expired'
               END as status
        FROM bus_passes
        ORDER BY created_at DESC
        LIMIT 10
    ''')
    passes = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(pass_data) for pass_data in passes])

@app.route('/admin/recent_activity')
@login_required
def admin_recent_activity():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    # Get recent activity
    cursor.execute('''
        SELECT username, action, timestamp
        FROM user_activity
        ORDER BY timestamp DESC
        LIMIT 10
    ''')
    activities = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(activity) for activity in activities])

@app.route('/help_support')
def help_support():
    try:
        return render_template('help_support.html')
    except Exception as e:
        print(f"Error rendering help_support.html: {str(e)}")
        return f"Error: {str(e)}", 500

@app.route('/admin/passes/delete/<pass_number>', methods=['DELETE'])
@login_required
def delete_pass(pass_number):
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Delete the pass
        cursor.execute('DELETE FROM bus_passes WHERE pass_number = ?', (pass_number,))
        conn.commit()
        return jsonify({'success': True, 'message': 'Pass deleted successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/admin/users/edit/<int:user_id>', methods=['PUT'])
@login_required
def edit_user(user_id):
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    current_user = cursor.fetchone()
    
    if not current_user or not current_user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        data = request.get_json()
        
        # Update user
        cursor.execute('''
            UPDATE users 
            SET username = ?, email = ?, is_admin = ?
            WHERE id = ?
        ''', (
            data.get('username'),
            data.get('email'),
            data.get('is_admin'),
            user_id
        ))
        
        conn.commit()
        return jsonify({'success': True, 'message': 'User updated successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/admin/users/delete/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    current_user = cursor.fetchone()
    
    if not current_user or not current_user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Delete user
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/admin/dashboard/export')
@login_required
def export_dashboard():
    # Check if user is admin
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_admin FROM users WHERE id = ?', (session['user_id'],))
    user = cursor.fetchone()
    
    if not user or not user['is_admin']:
        conn.close()
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        # Get all data for export
        cursor.execute('''
            SELECT 
                bp.pass_number,
                bp.name,
                bp.email,
                bp.district,
                bp.valid_until,
                CASE 
                    WHEN bp.valid_until >= date('now') THEN 'Active'
                    ELSE 'Expired'
                END as status,
                bp.created_at,
                u.username as created_by
            FROM bus_passes bp
            LEFT JOIN users u ON bp.user_id = u.id
            ORDER BY bp.created_at DESC
        ''')
        passes = cursor.fetchall()
        
        # Create CSV content
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['Pass Number', 'Name', 'Email', 'District', 'Valid Until', 'Status', 'Created At', 'Created By'])
        
        # Write data
        for pass_data in passes:
            writer.writerow([
                pass_data['pass_number'],
                pass_data['name'],
                pass_data['email'],
                pass_data['district'],
                pass_data['valid_until'],
                pass_data['status'],
                pass_data['created_at'],
                pass_data['created_by']
            ])
        
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=dashboard_export.csv'}
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

if __name__ == '__main__':
    app.debug = True  # Enable debug mode
    app.run(host='0.0.0.0', port=5000)