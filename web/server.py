#!/usr/bin/env python3

from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import json
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env.local")

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Configuration
LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")
DEFAULT_TRUNK_ID = os.getenv("SIP_OUTBOUND_TRUNK_ID")

@app.route('/')
def index():
    """Serve the main HTML page"""
    return app.send_static_file('index.html')

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "message": "Server is running"})

@app.route('/api/initiate-call', methods=['POST'])
def initiate_call():
    """Initiate a call using LiveKit dispatch"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['phone_number']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Prepare metadata
        metadata = {
            "phone_number": data['phone_number'],
            "trunk_id": data.get('trunk_id', DEFAULT_TRUNK_ID),
            "customer_name": data.get('customer_name', 'Alex'),
            "amount_due": data.get('amount_due', '1000.00'),
            "due_date": data.get('due_date', ''),
            "summary": data.get('summary', 'No past conversation')
        }
        
        # Execute lk dispatch command
        # Use the wrapper batch file that has access to lk in PATH
        metadata_json = json.dumps(metadata)
        
        # Build command using the batch file wrapper
        batch_file = os.path.join(os.path.dirname(__file__), 'call_lk.bat')
        cmd = [
            batch_file,
            'dispatch', 'create',
            '--new-room',
            '--agent-name', 'outbound-caller',
            '--metadata', metadata_json
        ]
        
        # Set environment variables for the command
        env = os.environ.copy()
        env['LIVEKIT_URL'] = LIVEKIT_URL
        env['LIVEKIT_API_KEY'] = LIVEKIT_API_KEY
        env['LIVEKIT_API_SECRET'] = LIVEKIT_API_SECRET
        
        # Run the command
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0:
            return jsonify({
                "success": True,
                "message": "Call initiated successfully",
                "output": result.stdout
            })
        else:
            return jsonify({
                "success": False,
                "error": result.stderr or "Failed to initiate call"
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Command timeout"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/call-history', methods=['GET'])
def call_history():
    """Get call history (placeholder - implement based on needs)"""
    return jsonify({"calls": []})

if __name__ == '__main__':
    print("🚀 Starting AI Voice Agent Web Server...")
    print(f"📡 Server running at: http://localhost:5000")
    print(f"🌐 Open the UI at: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
