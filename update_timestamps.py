import sqlite3
from datetime import datetime, timedelta

def update_timestamps():
    conn = sqlite3.connect('bus_pass.db')
    cursor = conn.cursor()
    
    try:
        # Get all activities
        cursor.execute('SELECT id, timestamp FROM user_activity')
        activities = cursor.fetchall()
        
        for activity_id, timestamp in activities:
            # Convert UTC timestamp to local time
            utc_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
            local_time = utc_time + timedelta(hours=5, minutes=30)  # IST is UTC+5:30
            
            # Update the timestamp
            cursor.execute('''
                UPDATE user_activity 
                SET timestamp = ? 
                WHERE id = ?
            ''', (local_time.strftime('%Y-%m-%d %H:%M:%S'), activity_id))
        
        conn.commit()
        print("Successfully updated timestamps to local time")
        
    except Exception as e:
        print(f"Error updating timestamps: {e}")
        conn.rollback()
    
    finally:
        conn.close()

if __name__ == '__main__':
    update_timestamps() 