import sqlite3
import qrcode
import os
import cv2
import datetime

# Database setup
conn = sqlite3.connect('bus_pass.db')
cursor = conn.cursor()

def verify_qr_code(image_path):
    """Verifies the QR code and displays user details."""
    # Load the image
    img = cv2.imread(image_path)

    # Detect QR code
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(img)

    if data:
        pass_number = data.split(":")[1].strip()  # Extract pass number from QR code

        cursor.execute("SELECT * FROM bus_passes WHERE pass_number = ?", (pass_number,))
        result = cursor.fetchone()

        if result:
            # Unpack the result tuple with the correct number of variables
            name, email, age, pass_number, qr_code, valid_until, id = result
            print(f"Name: {name}")
            print(f"Email: {email}")
            print(f"Age: {age}")
            print(f"Pass Number: {pass_number}")
            print(f"QR Code: {qr_code}")
            # Convert 'valid_until' to datetime.date for proper formatting
            valid_until = datetime.datetime.strptime(valid_until, '%Y-%m-%d').date() 
            print(f"Valid Until: {valid_until.strftime('%Y-%m-%d')}")
        else:
            print(f"Invalid QR code or pass number not found.")
    else:
        print("No QR code detected in the image.")

# Get the path to the QR code from the user
image_path = input("Enter the path to the QR code image: ")

# Verify the QR code
verify_qr_code(image_path)

# Close database connection
conn.close()
