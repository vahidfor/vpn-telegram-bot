#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database module for VPN Telegram Bot
Handles all database operations including user management, credits, and services.
"""

import sqlite3
import os
import threading
from contextlib import contextmanager
from typing import Optional, List, Tuple, Dict, Any
import datetime

# Database file path
DB_PATH = "vpn_bot.db"

# Thread-local storage for database connections
thread_local = threading.local()

def get_db_connection():
    """Get thread-local database connection"""
    if not hasattr(thread_local, 'connection'):
        thread_local.connection = sqlite3.connect(DB_PATH, check_same_thread=False)
        thread_local.connection.row_factory = sqlite3.Row
    return thread_local.connection

@contextmanager
def get_db():
    """Context manager for database operations"""
    conn = get_db_connection()
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        raise e
    else:
        conn.commit()

def init_database():
    """Initialize database with required tables"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone_number TEXT,
                full_name TEXT,
                requested_os TEXT,
                credit INTEGER DEFAULT 0,
                discount_used INTEGER DEFAULT 0,
                is_approved INTEGER DEFAULT 0,
                registration_date TEXT,
                last_activity TEXT
            )
        """)
        
        # Discount codes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                code TEXT PRIMARY KEY,
                value INTEGER,
                usage_count INTEGER DEFAULT 0,
                created_date TEXT
            )
        """)
        
        # Services table (for storing service content like configs or links)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS services (
                type TEXT PRIMARY KEY,
                content TEXT,
                is_file INTEGER DEFAULT 0,
                file_name TEXT
            )
        """)

        # Service prices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_prices (
                service_type TEXT PRIMARY KEY,
                price INTEGER
            )
        """)

        # Credit transfer history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS credit_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                receiver_id INTEGER,
                amount INTEGER,
                transfer_date TEXT,
                FOREIGN KEY (sender_id) REFERENCES users (id),
                FOREIGN KEY (receiver_id) REFERENCES users (id)
            )
        """)

        # Support messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS support_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message_text TEXT,
                message_date TEXT,
                is_answered INTEGER DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)

        # Purchase requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS purchase_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                account_type TEXT,
                request_date TEXT,
                status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        conn.commit()

# --- User Management ---

def add_user(user_id: int, username: str, first_name: str, last_name: str) -> None:
    """Add a new user if not exists, or update username/names if changed."""
    with get_db() as conn:
        cursor = conn.cursor()
        current_date = datetime.datetime.now().isoformat()
        cursor.execute(
            """INSERT OR IGNORE INTO users (id, username, first_name, last_name, registration_date, last_activity)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, username, first_name, last_name, current_date, current_date)
        )
        # Update username/names if user already exists but they changed
        cursor.execute(
            """UPDATE users SET username = ?, first_name = ?, last_name = ?, last_activity = ?
               WHERE id = ?""",
            (username, first_name, last_name, current_date, user_id)
        )
        conn.commit()

def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve user details by ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        return dict(user) if user else None

def update_user_info(user_id: int, **kwargs) -> bool:
    """Update specific user information (phone_number, full_name, requested_os)."""
    with get_db() as conn:
        cursor = conn.cursor()
        set_clauses = []
        values = []
        for key, value in kwargs.items():
            if key in ['phone_number', 'full_name', 'requested_os']:
                set_clauses.append(f"{key} = ?")
                values.append(value)
        
        if not set_clauses:
            return False # No valid fields to update
            
        values.append(user_id)
        query = f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?"
        
        try:
            cursor.execute(query, tuple(values))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"Database error during user info update: {e}")
            return False

def update_user_activity(user_id: int) -> None:
    """Update the last activity timestamp for a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        current_date = datetime.datetime.now().isoformat()
        cursor.execute("UPDATE users SET last_activity = ? WHERE id = ?", (current_date, user_id))
        conn.commit()

def approve_user(user_id: int) -> bool:
    """Approve a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET is_approved = 1 WHERE id = ?", (user_id,))
            conn.commit()
            return True
        except sqlite3.Error:
            return False

def reject_user(user_id: int) -> bool:
    """Reject a user (set is_approved to 0 again)."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET is_approved = 0 WHERE id = ?", (user_id,))
            conn.commit()
            return True
        except sqlite3.Error:
            return False

def get_all_users() -> List[Dict[str, Any]]:
    """Get all users."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users")
        return [dict(row) for row in cursor.fetchall()]

def get_pending_users() -> List[Dict[str, Any]]:
    """Get users who are not yet approved."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE is_approved = 0")
        return [dict(row) for row in cursor.fetchall()]

def increase_credit(user_id: int, amount: int) -> bool:
    """Increase user's credit."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE users SET credit = credit + ? WHERE id = ?", (amount, user_id))
            conn.commit()
            return True
        except sqlite3.Error:
            return False

def decrease_credit(user_id: int, amount: int) -> bool:
    """Decrease user's credit, ensuring it doesn't go below zero."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT credit FROM users WHERE id = ?", (user_id,))
            current_credit = cursor.fetchone()[0]
            if current_credit >= amount:
                cursor.execute("UPDATE users SET credit = credit - ? WHERE id = ?", (amount, user_id))
                conn.commit()
                return True
            else:
                return False # Not enough credit
        except (sqlite3.Error, TypeError): # TypeError if fetchone()[0] fails (user not found)
            return False

# --- Discount Codes ---

def add_discount_code(code: str, value: int) -> bool:
    """Add a new discount code."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            current_date = datetime.datetime.now().isoformat()
            cursor.execute(
                "INSERT INTO discount_codes (code, value, created_date) VALUES (?, ?, ?)",
                (code, value, current_date)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError: # Code already exists
            return False
        except sqlite3.Error:
            return False

def get_discount_code(code: str) -> Optional[Dict[str, Any]]:
    """Retrieve a discount code."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM discount_codes WHERE code = ?", (code,))
        code_data = cursor.fetchone()
        return dict(code_data) if code_data else None

def use_discount_code(code: str) -> Optional[int]:
    """Apply a discount code and increment its usage count."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT value FROM discount_codes WHERE code = ?", (code,))
            result = cursor.fetchone()
            if result:
                value = result[0]
                cursor.execute("UPDATE discount_codes SET usage_count = usage_count + 1 WHERE code = ?", (code,))
                conn.commit()
                return value
            return None # Code not found
        except sqlite3.Error:
            conn.rollback()
            return None

def delete_discount_code(code: str) -> bool:
    """Delete a discount code."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM discount_codes WHERE code = ?", (code,))
            conn.commit()
            return cursor.rowcount > 0 # Returns True if a row was deleted
        except sqlite3.Error:
            return False

def get_all_discount_codes() -> List[Dict[str, Any]]:
    """Get all discount codes."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM discount_codes")
        return [dict(row) for row in cursor.fetchall()]

# --- Services (config/link storage) ---

def set_service(service_type: str, content: str, is_file: bool, file_name: Optional[str] = None) -> bool:
    """Set or update the content for a service type."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT OR REPLACE INTO services (type, content, is_file, file_name)
                   VALUES (?, ?, ?, ?)""",
                (service_type, content, 1 if is_file else 0, file_name)
            )
            conn.commit()
            return True
        except sqlite3.Error:
            return False

def get_service(service_type: str) -> Optional[Dict[str, Any]]:
    """Retrieve service content by type."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM services WHERE type = ?", (service_type,))
        service = cursor.fetchone()
        return dict(service) if service else None

def delete_service(service_type: str) -> bool:
    """Delete a service."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM services WHERE type = ?", (service_type,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False

def get_all_services() -> List[Dict[str, Any]]:
    """Get all defined services."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM services")
        return [dict(row) for row in cursor.fetchall()]


# --- Service Prices ---

def set_service_price(service_type: str, price: int) -> bool:
    """Set or update the price for a service type."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT OR REPLACE INTO service_prices (service_type, price)
                   VALUES (?, ?)""",
                (service_type, price)
            )
            conn.commit()
            return True
        except sqlite3.Error:
            return False

def get_service_price(service_type: str) -> Optional[int]:
    """Retrieve the price for a service type."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT price FROM service_prices WHERE service_type = ?", (service_type,))
        result = cursor.fetchone()
        return result[0] if result else None

def get_all_service_prices() -> Dict[str, int]:
    """Get all defined service prices."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT service_type, price FROM service_prices")
        return {row[0]: row[1] for row in cursor.fetchall()}

# --- Credit Transfers ---

def add_credit_transfer(sender_id: int, receiver_id: int, amount: int) -> bool:
    """Record a credit transfer."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            current_date = datetime.datetime.now().isoformat()
            cursor.execute(
                """INSERT INTO credit_transfers (sender_id, receiver_id, amount, transfer_date)
                   VALUES (?, ?, ?, ?)""",
                (sender_id, receiver_id, amount, current_date)
            )
            conn.commit()
            return True
        except sqlite3.Error:
            return False

def get_credit_transfers_for_user(user_id: int) -> List[Dict[str, Any]]:
    """Get all credit transfers for a given user (as sender or receiver)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT * FROM credit_transfers WHERE sender_id = ? OR receiver_id = ?
               ORDER BY transfer_date DESC""",
            (user_id, user_id)
        )
        return [dict(row) for row in cursor.fetchall()]

# --- Support Messages ---

def add_support_message(user_id: int, message_text: str) -> bool:
    """Add a new support message from a user."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            current_date = datetime.datetime.now().isoformat()
            cursor.execute(
                """INSERT INTO support_messages (user_id, message_text, message_date)
                   VALUES (?, ?, ?)""",
                (user_id, message_text, current_date)
            )
            conn.commit()
            return True
        except sqlite3.Error:
            return False

def get_support_message_by_id(message_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a support message by its ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM support_messages WHERE id = ?", (message_id,))
        msg = cursor.fetchone()
        return dict(msg) if msg else None

def get_support_messages(answered: Optional[bool] = None) -> List[Dict[str, Any]]:
    """Get support messages, optionally filtered by answered status."""
    with get_db() as conn:
        cursor = conn.cursor()
        if answered is None:
            cursor.execute("SELECT * FROM support_messages ORDER BY message_date DESC")
        else:
            status = 1 if answered else 0
            cursor.execute("SELECT * FROM support_messages WHERE is_answered = ? ORDER BY message_date DESC", (status,))
        return [dict(row) for row in cursor.fetchall()]

def mark_support_message_answered(message_id: int) -> bool:
    """Mark a support message as answered."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE support_messages SET is_answered = 1 WHERE id = ?", (message_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False

# --- Purchase Requests ---

def add_purchase_request(user_id: int, account_type: str, requested_service: str, requested_device: str, status: str = 'pending') -> int:
    """Add a new purchase request and return its ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            current_date = datetime.datetime.now().isoformat()
            cursor.execute(
                """INSERT INTO purchase_requests (user_id, account_type, requested_service, requested_device, request_date, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (user_id, account_type, requested_service, requested_device, current_date, status)
            )
            conn.commit()
            return cursor.lastrowid # Return the ID of the new row
        except sqlite3.Error:
            return 0 # Indicate failure

def get_purchase_request_by_id(request_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a purchase request by its ID."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM purchase_requests WHERE id = ?", (request_id,))
        request = cursor.fetchone()
        return dict(request) if request else None

def get_purchase_requests_by_user(user_id: int) -> List[Dict[str, Any]]:
    """Retrieve all purchase requests for a specific user."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM purchase_requests WHERE user_id = ? ORDER BY request_date DESC", (user_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_purchase_requests_by_status(status: str) -> List[Dict[str, Any]]:
    """Retrieve purchase requests filtered by status ('pending', 'approved', 'rejected')."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM purchase_requests WHERE status = ? ORDER BY request_date DESC", (status,))
        return [dict(row) for row in cursor.fetchall()]

def update_purchase_request_status(request_id: int, new_status: str) -> bool:
    """Update the status of a purchase request."""
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("UPDATE purchase_requests SET status = ? WHERE id = ?", (new_status, request_id))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error:
            return False


# --- Bot Statistics ---

def get_bot_statistics() -> Dict[str, Any]:
    """Get bot statistics"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Total users
            cursor.execute("SELECT COUNT(*) FROM users")
            total_users = cursor.fetchone()[0]
            
            # Approved users
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_approved = 1")
            approved_users = cursor.fetchone()[0]
            
            # Pending users
            cursor.execute("SELECT COUNT(*) FROM users WHERE is_approved = 0")
            pending_users = cursor.fetchone()[0]
            
            # Total credit (sum of all users' credits)
            cursor.execute("SELECT SUM(credit) FROM users")
            total_credit = cursor.fetchone()[0] or 0 # Use 0 if SUM is NULL (no users)
            
            # Total discount codes
            cursor.execute("SELECT COUNT(*) FROM discount_codes")
            total_discount_codes = cursor.fetchone()[0]
            
            # Total support messages
            cursor.execute("SELECT COUNT(*) FROM support_messages")
            total_support_messages = cursor.fetchone()[0]
            
            return {
                'total_users': total_users,
                'approved_users': approved_users,
                'pending_users': pending_users,
                'total_credit': total_credit,
                'total_discount_codes': total_discount_codes,
                'total_support_messages': total_support_messages
            }
    except sqlite3.Error:
        return {}
