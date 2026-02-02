import sqlite3
import json
import logging

logger = logging.getLogger(__name__)

def get_connection():
    conn = sqlite3.connect('bluesignal.db', check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT,
            authenticity_score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            media_url TEXT,
            latitude REAL,
            longitude REAL,
            location_name TEXT,
            status TEXT DEFAULT 'processing',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            urgency_level TEXT,
            flood_type TEXT,
            confidence_score REAL,
            verified INTEGER DEFAULT 0,
            ai_summary TEXT,
            latitude REAL,
            longitude REAL,
            location_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            vote_type TEXT NOT NULL CHECK (vote_type IN ('up', 'down')),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts (id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(post_id, user_id)
        )
    ''')
    
    import hashlib
    
    demo_users = [
        ('admin', 'admin@bluesignal.gov', 'admin123', 'authority', 'System Admin', 0),
        ('floodwatcher', 'watcher@example.com', 'password123', 'citizen', 'Sarah Johnson', 15),
        ('mumbai_resident', 'resident@example.com', 'password123', 'citizen', 'Raj Patel', 8),
        ('weather_alert', 'weather@example.com', 'password123', 'citizen', 'Mike Chen', 22),
        ('city_monitor', 'monitor@example.com', 'password123', 'citizen', 'Lisa Kumar', -3),
        ('flood_reporter', 'reporter@example.com', 'password123', 'citizen', 'David Singh', 12)
    ]
    
    for username, email, password, role, full_name, score in demo_users:
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        if not cursor.fetchone():
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            cursor.execute('''
                INSERT INTO users (username, email, password, role, full_name, authenticity_score)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (username, email, hashed_password, role, full_name, score))
    
    demo_posts = [
        (2, 'Severe flooding on Main Street', 'Water is knee-deep and cars are getting stuck. Please avoid the area! Emergency services are on the way.', 19.0760, 72.8777, 'Mumbai Central'),
        (3, 'Flash flood warning', 'Heavy rain causing rapid water accumulation in downtown area. Stay safe everyone!', 19.0176, 72.8562, 'Mumbai Downtown'),
        (4, 'Urban flooding near railway station', 'Drainage system overwhelmed by heavy rainfall. Traffic disrupted.', 19.0596, 72.8295, 'Mumbai Railway Station'),
        (5, 'False alarm - no flooding here', 'Just some puddles, nothing serious. People are overreacting.', 19.0760, 72.8777, 'Mumbai Central'),
        (6, 'River overflow causing flooding', 'River levels rising steadily. Residential areas affected.', 19.0176, 72.8562, 'Mumbai River Area'),
        (2, 'Update: Flood situation improving', 'Water levels are receding. Roads becoming accessible again.', 19.0596, 72.8295, 'Mumbai Downtown'),
        (4, 'Heavy rain continues', 'More rainfall expected. Stay indoors if possible.', 19.0760, 72.8777, 'Mumbai Central'),
        (3, 'Emergency evacuation in progress', 'Authorities evacuating low-lying areas. Follow official instructions.', 19.0176, 72.8562, 'Mumbai River Area')
    ]
    
    for user_id, title, description, lat, lng, location in demo_posts:
        cursor.execute('''
            INSERT INTO posts (user_id, title, description, latitude, longitude, location_name, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, title, description, lat, lng, location, 'verified'))
    
    conn.commit()
    conn.close()
    logger.info("Database initialized with demo data")

def create_user(username, email, password, role, full_name):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO users (username, email, password, role, full_name) VALUES (?, ?, ?, ?, ?)',
                      (username, email, password, role, full_name))
        conn.commit()
        user_id = cursor.lastrowid
        return user_id
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return None
    finally:
        conn.close()

def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return dict(user)
    return None

def create_post(user_id, title, description, media_url, latitude, longitude, location_name):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO posts (user_id, title, description, media_url, latitude, longitude, location_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, title, description, media_url, latitude, longitude, location_name))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error creating post: {e}")
        return None
    finally:
        conn.close()

def update_post_status(post_id, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE posts SET status = ? WHERE id = ?', (status, post_id))
    conn.commit()
    conn.close()

def get_posts_by_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, u.username FROM posts p
        JOIN users u ON p.user_id = u.id
        WHERE p.user_id = ? ORDER BY p.created_at DESC
    ''', (user_id,))
    posts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return posts

def get_all_posts_with_votes():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.*, u.username, u.authenticity_score,
               COALESCE(SUM(CASE WHEN v.vote_type = 'up' THEN 1 ELSE 0 END), 0) as upvotes,
               COALESCE(SUM(CASE WHEN v.vote_type = 'down' THEN 1 ELSE 0 END), 0) as downvotes
        FROM posts p
        JOIN users u ON p.user_id = u.id
        LEFT JOIN votes v ON p.id = v.post_id
        GROUP BY p.id
        ORDER BY p.created_at DESC
    ''')
    posts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return posts

def vote_post(post_id, user_id, vote_type):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT vote_type FROM votes WHERE post_id = ? AND user_id = ?', (post_id, user_id))
        existing_vote = cursor.fetchone()
        
        if existing_vote:
            cursor.execute('UPDATE votes SET vote_type = ?, updated_at = CURRENT_TIMESTAMP WHERE post_id = ? AND user_id = ?', 
                         (vote_type, post_id, user_id))
        else:
            cursor.execute('INSERT INTO votes (post_id, user_id, vote_type) VALUES (?, ?, ?)', 
                         (post_id, user_id, vote_type))
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error voting on post: {e}")
        return False
    finally:
        conn.close()

def get_user_profile(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    if user:
        user_dict = dict(user)
        
        cursor.execute('''
            SELECT p.*, 
                   COALESCE(SUM(CASE WHEN v.vote_type = 'up' THEN 1 ELSE 0 END), 0) as upvotes,
                   COALESCE(SUM(CASE WHEN v.vote_type = 'down' THEN 1 ELSE 0 END), 0) as downvotes
            FROM posts p
            LEFT JOIN votes v ON p.id = v.post_id
            WHERE p.user_id = ?
            GROUP BY p.id
            ORDER BY p.created_at DESC
        ''', (user_id,))
        posts = [dict(row) for row in cursor.fetchall()]
        user_dict['posts'] = posts
        
        conn.close()
        return user_dict
    conn.close()
    return None

def get_user_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return dict(user)
    return None

def create_report(post_id, user_id, urgency_level, flood_type, confidence_score, verified, ai_summary, latitude, longitude, location_name):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO reports (post_id, user_id, urgency_level, flood_type, confidence_score, verified, ai_summary, latitude, longitude, location_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (post_id, user_id, urgency_level, flood_type, confidence_score, verified, ai_summary, latitude, longitude, location_name))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error creating report: {e}")
        return None
    finally:
        conn.close()

def get_all_reports():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.*, p.title, p.description, p.media_url, p.status, u.username
        FROM reports r
        JOIN posts p ON r.post_id = p.id
        JOIN users u ON r.user_id = u.id
        ORDER BY r.created_at DESC
    ''')
    reports = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return reports

def get_post_by_id(post_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM posts WHERE id = ?', (post_id,))
    post = cursor.fetchone()
    conn.close()
    if post:
        return dict(post)
    return None


def get_reports_for_map():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            r.id,
            r.post_id,
            p.title,
            p.description,
            r.urgency_level,
            r.flood_type,
            r.ai_summary,
            r.latitude,
            r.longitude,
            r.location_name,
            p.status
        FROM reports r
        JOIN posts p ON r.post_id = p.id
        ORDER BY r.created_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

