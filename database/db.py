import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "calmmind.db")

def get_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Access columns by name
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Initializes the database schema."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Create chat_sessions table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create chat_messages table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            message_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mood TEXT,
            stress_level TEXT,
            confidence_score REAL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
        )
    """)
    
    # Create mood_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mood_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            mood TEXT NOT NULL,
            stress_level TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

def create_session(session_id, title):
    """Creates a new chat session."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO chat_sessions (session_id, title) VALUES (?, ?)",
                (session_id, title)
            )
    except sqlite3.IntegrityError:
        pass  # Session already exists
    finally:
        conn.close()

def delete_session(session_id):
    """Deletes a session and all its messages (cascades via foreign key)."""
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
    conn.close()

def get_all_sessions():
    """Retrieves all chat sessions sorted by created_at descending."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM chat_sessions ORDER BY created_at DESC")
    sessions = cursor.fetchall()
    conn.close()
    return sessions

def get_session_messages(session_id):
    """Retrieves all messages for a specific session."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY message_id ASC",
        (session_id,)
    )
    messages = cursor.fetchall()
    conn.close()
    return messages

def add_message(session_id, role, content, mood=None, stress_level=None, confidence_score=None):
    """Adds a new message to the session."""
    conn = get_connection()
    with conn:
        conn.execute(
            """
            INSERT INTO chat_messages (session_id, role, content, mood, stress_level, confidence_score)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, role, content, mood, stress_level, confidence_score)
        )
    conn.close()

def add_mood_log(session_id, mood, stress_level, confidence_score):
    """Adds a log entry for tracked moods."""
    conn = get_connection()
    with conn:
        conn.execute(
            """
            INSERT INTO mood_logs (session_id, mood, stress_level, confidence_score)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, mood, stress_level, confidence_score)
        )
    conn.close()

def get_mood_logs():
    """Retrieves all logged moods for analytics."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM mood_logs ORDER BY timestamp ASC")
    logs = cursor.fetchall()
    conn.close()
    return logs

def update_session_title(session_id, title):
    """Updates the title of a chat session."""
    conn = get_connection()
    with conn:
        conn.execute(
            "UPDATE chat_sessions SET title = ? WHERE session_id = ?",
            (title, session_id)
        )
    conn.close()
