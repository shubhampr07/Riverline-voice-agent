#!/usr/bin/env python3

from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import json
import os
import sys
import asyncio
from dotenv import load_dotenv

# Add parent directory to path to import analyzer
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from analyzer import ConversationAnalyzer

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

@app.route('/api/transcripts', methods=['GET'])
def list_transcripts():
    """List all available transcript files"""
    try:
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        
        if not os.path.exists(logs_dir):
            return jsonify({"transcripts": []})
        
        transcripts = []
        for filename in os.listdir(logs_dir):
            if filename.startswith("transcript_") and filename.endswith(".json"):
                file_path = os.path.join(logs_dir, filename)
                file_stat = os.stat(file_path)
                
                transcripts.append({
                    "filename": filename,
                    "created_at": file_stat.st_ctime,
                    "size": file_stat.st_size,
                    "path": file_path
                })
        
        # Sort by creation time, newest first
        transcripts.sort(key=lambda x: x['created_at'], reverse=True)
        
        return jsonify({"transcripts": transcripts})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze/<filename>', methods=['GET'])
def analyze_transcript(filename):
    """Analyze a specific transcript file"""
    try:
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        file_path = os.path.join(logs_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Transcript not found"}), 404
        
        # Run async analysis
        analyzer = ConversationAnalyzer()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        analysis = loop.run_until_complete(analyzer.analyze_transcript_file(file_path))
        loop.close()
        
        return jsonify(analysis)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze-all', methods=['GET'])
def analyze_all_transcripts():
    """Analyze all transcript files"""
    try:
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        
        analyzer = ConversationAnalyzer()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(analyzer.batch_analyze(logs_dir))
        loop.close()
        
        return jsonify({"analyses": results, "total": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/analysis-summary', methods=['GET'])
def analysis_summary():
    """Get summary statistics from all analyses"""
    try:
        logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        
        analyzer = ConversationAnalyzer()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(analyzer.batch_analyze(logs_dir))
        loop.close()
        
        # Calculate summary statistics
        total_calls = len(results)
        successful_analyses = len([r for r in results if "error" not in r])
        
        if successful_analyses == 0:
            return jsonify({
                "total_calls": total_calls,
                "successful_analyses": 0,
                "message": "No successful analyses"
            })
        
        # Aggregate metrics
        avg_sentiment = sum([r.get("sentiment_analysis", {}).get("sentiment_score", 0) 
                            for r in results if "error" not in r]) / successful_analyses
        
        avg_satisfaction = sum([r.get("predictions", {}).get("customer_satisfaction", 0) 
                               for r in results if "error" not in r]) / successful_analyses
        
        avg_payment_prob = sum([r.get("predictions", {}).get("payment_probability", 0) 
                               for r in results if "error" not in r]) / successful_analyses
        
        outcomes = {}
        for r in results:
            if "error" not in r:
                outcome = r.get("performance_metrics", {}).get("call_outcome", "unknown")
                outcomes[outcome] = outcomes.get(outcome, 0) + 1
        
        return jsonify({
            "total_calls": total_calls,
            "successful_analyses": successful_analyses,
            "average_sentiment_score": round(avg_sentiment, 2),
            "average_customer_satisfaction": round(avg_satisfaction, 2),
            "average_payment_probability": round(avg_payment_prob, 2),
            "outcomes": outcomes
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    print("🚀 Starting AI Voice Agent Web Server...")
    print(f"📡 Server running at: http://localhost:5000")
    print(f"🌐 Open the UI at: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server")
    
    app.run(host='0.0.0.0', port=5000, debug=True)
