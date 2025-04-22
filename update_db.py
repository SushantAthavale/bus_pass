import sqlite3

def update_paths():
    conn = sqlite3.connect('bus_pass.db')
    cursor = conn.cursor()
    
    # Update QR code paths
    cursor.execute("""
        UPDATE bus_passes 
        SET qr_code = 'qr_codes/' || qr_code 
        WHERE qr_code NOT LIKE 'qr_codes/%'
    """)
    
    # Update image paths
    cursor.execute("""
        UPDATE bus_passes 
        SET image_path = 'user_images/' || image_path 
        WHERE image_path IS NOT NULL AND image_path NOT LIKE 'user_images/%'
    """)
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    update_paths() 