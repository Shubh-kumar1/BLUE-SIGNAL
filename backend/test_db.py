import sqlite3
import hashlib

def test_database():
    conn = sqlite3.connect('bluesignal.db')
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    print("Users table columns:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    test_password = hashlib.sha256('testpass123'.encode()).hexdigest()
    try:
        cursor.execute('''
            INSERT INTO users (username, email, password, role, full_name)
            VALUES (?, ?, ?, ?, ?)
        ''', ('testuser', 'test@example.com', test_password, 'citizen', 'Test User'))
        conn.commit()
        print("✅ User creation test passed!")
        
        cursor.execute('DELETE FROM users WHERE username = ?', ('testuser',))
        conn.commit()
        print("✅ Test user cleaned up!")
        
    except Exception as e:
        print(f"❌ User creation test failed: {e}")
    
    conn.close()

if __name__ == "__main__":
    test_database()
