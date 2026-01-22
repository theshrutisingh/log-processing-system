
import sqlite3
import bcrypt
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "users.db")

def init_db():
    """Initialize the users database."""
    # Ensure data directory exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            email TEXT
        )
    ''')
    conn.commit()
    conn.close()

def create_user(username, password, email=""):
    """Create a new user with hashed password. Returns True if success, False if username exists."""
    # Encode password to bytes for hashing
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)", 
                  (username, hashed_password, email))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def check_credentials(username, password):
    """Check if username and password match. Returns True if valid."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Check username OR email
    c.execute("SELECT password FROM users WHERE username = ? OR email = ?", (username, username))
    result = c.fetchone()
    conn.close()
    
    if result:
        stored_hash = result[0]
        # Check password
        if isinstance(stored_hash, str):
            stored_hash = stored_hash.encode('utf-8')
        try:
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash)
        except ValueError:
            # Handle invalid hash format gracefully
            return False
    return False

def check_email_exists(email):
    """Check if an email is registered. Returns username if found, else None."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE email = ?", (email,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def update_password(email, new_password):
    """Update password for the given email. Returns True if success."""
    # Hash new password
    password_bytes = new_password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("UPDATE users SET password = ? WHERE email = ?", (hashed_password, email))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating password: {e}")
        return False
    finally:
        conn.close()

def get_user_email(username):
    """Retrieve the email address for a given username."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT email FROM users WHERE username = ?", (username,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

def get_canonical_username(identifier):
    """Retrieve the canonical username for a given identifier (username or email)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE username = ? OR email = ?", (identifier, identifier))
    result = c.fetchone()
    conn.close()
    return result[0] if result else identifier
