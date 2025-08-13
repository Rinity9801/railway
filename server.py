from flask import Flask, request, jsonify
import os
import psycopg2
from urllib.parse import urlparse
import hashlib
import time

app = Flask(__name__)

# Railway provides DATABASE_URL automatically
DATABASE_URL = os.environ.get('DATABASE_URL')

def init_database():
    """Initialize database table"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Create licenses table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                id SERIAL PRIMARY KEY,
                discord_id BIGINT NOT NULL,
                minecraft_uuid VARCHAR(32) NOT NULL UNIQUE,
                username VARCHAR(16) NOT NULL,
                hwid VARCHAR(64),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database init error: {e}")

@app.route('/')
def home():
    return "RouteWalker License Server - Running ✅"

@app.route('/verify', methods=['POST'])
def verify_license():
    try:
        data = request.json
        uuid = data.get('uuid', '').lower().replace('-', '')
        hwid = data.get('hwid', '')
        
        if not uuid or not hwid:
            return jsonify({"valid": False, "reason": "Missing UUID or HWID"})
        
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Check if UUID exists in database
        cur.execute("SELECT hwid, username FROM licenses WHERE minecraft_uuid = %s", (uuid,))
        result = cur.fetchone()
        
        if not result:
            conn.close()
            return jsonify({
                "valid": False, 
                "reason": "UUID not licensed",
                "uuid": uuid[:8] + "..."
            })
        
        stored_hwid, username = result
        
        # Bind hardware on first use
        if not stored_hwid:
            cur.execute("UPDATE licenses SET hwid = %s WHERE minecraft_uuid = %s", (hwid, uuid))
            conn.commit()
            conn.close()
            print(f"✅ Hardware bound for {username} ({uuid[:8]}...)")
            return jsonify({
                "valid": True, 
                "reason": "Hardware bound successfully",
                "username": username
            })
        
        # Verify hardware match
        valid = stored_hwid == hwid
        conn.close()
        
        if valid:
            print(f"✅ License verified for {username} ({uuid[:8]}...)")
            return jsonify({
                "valid": True, 
                "reason": "License verified",
                "username": username
            })
        else:
            print(f"❌ Hardware mismatch for {username} ({uuid[:8]}...)")
            return jsonify({
                "valid": False, 
                "reason": "Hardware mismatch - license bound to different computer"
            })
            
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return jsonify({
            "valid": False, 
            "reason": f"Server error: {str(e)}"
        })

@app.route('/add_license', methods=['POST'])
def add_license():
    """Add new license (called by Discord bot)"""
    try:
        data = request.json
        discord_id = data.get('discord_id')
        minecraft_uuid = data.get('minecraft_uuid', '').lower().replace('-', '')
        username = data.get('username')
        
        if not all([discord_id, minecraft_uuid, username]):
            return jsonify({"success": False, "reason": "Missing required fields"})
        
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        
        # Insert new license (or update existing)
        cur.execute("""
            INSERT INTO licenses (discord_id, minecraft_uuid, username) 
            VALUES (%s, %s, %s)
            ON CONFLICT (minecraft_uuid) 
            DO UPDATE SET discord_id = %s, username = %s
        """, (discord_id, minecraft_uuid, username, discord_id, username))
        
        conn.commit()
        conn.close()
        
        print(f"✅ License added for {username} ({minecraft_uuid[:8]}...)")
        return jsonify({"success": True, "reason": "License added"})
        
    except Exception as e:
        print(f"❌ Add license error: {e}")
        return jsonify({"success": False, "reason": str(e)})

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM licenses")
        count = cur.fetchone()[0]
        conn.close()
        
        return jsonify({
            "status": "healthy",
            "database": "connected",
            "total_licenses": count
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "database": "disconnected",
            "error": str(e)
        }), 500

if __name__ == '__main__':
    # Initialize database on startup
    init_database()
    
    # Get port from environment (Railway sets this)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
