import sqlite3
import qrcode
import os
import datetime
import cv2
import random
import hashlib
import base64
import secrets
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, session, jsonify
from werkzeug.security import generate_password_hash

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
            photo_data TEXT,  -- Store base64 image data
            qr_code TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

def generate_otp():
    """Generates a 6-digit OTP."""
    return str(random.randint(100000, 999999))

def verify_otp(email, mobile, otp):
    """Verify the OTP entered by the user."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get the most recent OTP for the user (within last 5 minutes)
        cursor.execute('''
            SELECT otp FROM otp_verification 
            WHERE email = ? AND mobile = ? 
            AND created_at >= datetime('now', '-5 minutes')
            ORDER BY created_at DESC LIMIT 1
        ''', (email, mobile))
        
        result = cursor.fetchone()
        
        if result and str(result[0]) == str(otp):
            # Delete the used OTP
            cursor.execute('''
                DELETE FROM otp_verification 
                WHERE email = ? AND mobile = ? AND otp = ?
            ''', (email, mobile, otp))
            
            conn.commit()
            return True
            
        return False
        
    except Exception as e:
        print(f"Error verifying OTP: {str(e)}")
        if conn:
            conn.rollback()
        return False
        
    finally:
        if conn:
            conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
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
                    return redirect(url_for('display_pass', pass_number=pass_number))
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

@app.route('/view_pass', methods=['GET'])
def view_pass():
    """Render the view pass search page."""
    return render_template('view_pass.html')

@app.route('/renew', methods=['GET'])
def renew():
    """Render the renew pass search page."""
    return render_template('renew.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)