# 🎙️ Riverline Voice Agent

An AI-powered voice agent for automated outbound calling with real-time conversation capabilities. This system uses LiveKit for telephony, Google Gemini for intelligent conversation, and advanced speech processing for natural interactions.

---

## 📋 Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Setup Guide](#-setup-guide)
- [Getting API Keys](#-getting-api-keys)
- [Running the Agent](#-running-the-agent)
- [Making Calls](#-making-calls)
- [Code Structure](#-code-structure)
- [Troubleshooting](#-troubleshooting)

---

## ✨ Features

- **Outbound Calling**: Make automated calls to real phone numbers via SIP trunks
- **AI-Powered Conversations**: Natural language understanding using Google Gemini
- **Real-time Speech Processing**:
  - Speech-to-Text: Deepgram
  - Text-to-Speech: Cartesia (Sonic-2 model)
  - Voice Activity Detection: Silero
- **Call Analysis**: Automatic post-call analysis with sentiment, predictions, and insights
- **Web Dashboard**: User-friendly interface to initiate calls and view analytics
- **Transcript Logging**: Complete conversation history saved as JSON

---

## 🏗️ Architecture

The project consists of three main components:

### 1. **Agent Worker** (`agent.py`)
The core AI agent that handles conversations. It:
- Connects to LiveKit rooms when calls are initiated
- Processes audio using STT (Speech-to-Text)
- Generates responses using Google Gemini LLM
- Converts responses to speech using TTS (Text-to-Speech)
- Provides function tools like `log_complaint()`, `reschedule_call()`, and `end_call()`
- Saves complete transcripts after each call

### 2. **Web Server** (`web/server.py`)
Flask-based backend that:
- Serves the web dashboard UI
- Dispatches new calls via LiveKit API
- Lists and manages call transcripts
- Triggers conversation analysis
- Provides REST API endpoints for the frontend

### 3. **Analyzer** (`analyzer.py`)
Post-call analysis module that:
- Processes conversation transcripts
- Uses Google Gemini to analyze sentiment, quality, and outcomes
- Generates predictions (payment probability, customer satisfaction, etc.)
- Saves analysis results to the `predictions/` folder

---

## 🚀 Setup Guide

### Prerequisites

- **Python 3.8+** installed
- **LiveKit CLI** installed (for terminal-based calling)
- **SIP Trunk** provider (Twilio, Telnyx, etc.)
- API keys for: LiveKit, Google Gemini, Deepgram, Cartesia

### Step 1: Clone and Install Dependencies

```bash
git clone <repository-url>
cd Riverline-agent

# Install Python dependencies
pip install -r requirements.txt

# Install web server dependencies
pip install flask flask-cors
```

### Step 2: Install LiveKit CLI

The LiveKit CLI is required for creating SIP trunks and triggering calls from the terminal.

**Installation:**
```bash
# macOS/Linux
brew install livekit-cli

# Windows (using Scoop)
scoop install livekit-cli

# Or download from: https://github.com/livekit/livekit-cli/releases
```

Verify installation:
```bash
lk --version
```

### Step 3: Configure Environment Variables

Create a `.env.local` file in the root directory:

```bash
cp .env.example .env.local
```

Edit `.env.local` with your credentials:

```env
# LiveKit Configuration
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxxxx
LIVEKIT_API_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# SIP Trunk ID (obtained after creating trunk)
SIP_OUTBOUND_TRUNK_ID=ST_xxxxxxxxxxxx

# API Keys
DEEPGRAM_API_KEY=your_deepgram_key
CARTESIA_API_KEY=your_cartesia_key
GEMINI_API_KEY=your_gemini_key
```

### Step 4: Create SIP Trunk

You need to create a SIP trunk in LiveKit to connect to your telephony provider.

**Edit `outbound-trunk.json`** with your SIP provider details:
```json
{
  "trunk": {
    "name": "Customer Support",
    "address": "your-provider.pstn.twilio.com",
    "numbers": [
      "+1234567890"
    ],
    "auth_username": "your_username",
    "auth_password": "your_password"
  }
}
```

**Create the trunk:**
```bash
lk sip outbound create outbound-trunk.json
```

This command will return a **Trunk ID** (e.g., `ST_xxxxxxxxxxxx`). Copy this ID and add it to your `.env.local` file as `SIP_OUTBOUND_TRUNK_ID`.

---

## 🔑 Getting API Keys

### LiveKit
1. Go to [livekit.io](https://livekit.io/) and create an account
2. Create a new project
3. Navigate to **Settings** → **Keys**
4. Copy your `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET`

### Google Gemini
1. Visit [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click **"Get API Key"**
3. Create a new API key or use an existing one
4. Copy the key as `GEMINI_API_KEY`

### Deepgram
1. Sign up at [deepgram.com](https://deepgram.com/)
2. Go to **API Keys** in your dashboard
3. Create a new API key
4. Copy as `DEEPGRAM_API_KEY`

### Cartesia
1. Sign up at [cartesia.ai](https://cartesia.ai/)
2. Navigate to your dashboard
3. Generate an API key
4. Copy as `CARTESIA_API_KEY`

---

## 🏃‍♂️ Running the Agent

You need to run **two processes** simultaneously:

### Terminal 1: Start the Agent Worker

```bash
python agent.py dev
```

This starts the agent in development mode, waiting for incoming call jobs from LiveKit.

**Expected output:**
```
INFO:outbound-caller:connecting to room...
```

### Terminal 2: Start the Web Server

```bash
python web/server.py
```

**Expected output:**
```
🚀 Starting AI Voice Agent Web Server...
📡 Server running at: http://localhost:5000
🌐 Open the UI at: http://localhost:5000
```

Open your browser and navigate to **http://localhost:5000**

---

## 📞 Making Calls

### Option 1: Using the Web UI (Recommended)

1. Open **http://localhost:5000** in your browser
2. Fill in the call details:
   - **Phone Number**: E.164 format (e.g., `+15550001234`)
   - **Customer Name**: Name for personalization
   - **Amount Due**: Context for the conversation
   - **Due Date**: Payment due date
3. Click **"Initiate Call"**
4. The system will dispatch the call and the agent will handle the conversation

### Option 2: Using LiveKit CLI (Terminal)

You can trigger calls directly from the terminal:

```bash
lk dispatch create \
  --new-room \
  --agent-name outbound-caller \
  --metadata "{\"phone_number\": \"+15550001234\", \"customer_name\": \"John Doe\", \"amount_due\": \"500.00\"}"
```

**Metadata parameters:**
- `phone_number` (required): Destination phone number in E.164 format
- `customer_name` (optional): Customer's name
- `amount_due` (optional): Outstanding amount
- `due_date` (optional): Payment due date
- `summary` (optional): Previous conversation summary

---

## 📁 Code Structure

### Main Files

- **`agent.py`**: Core agent logic
  - `OutboundCaller` class: Defines the AI agent persona and behavior
  - `entrypoint()`: Main function that connects to LiveKit, initiates calls, and manages sessions
  - Function tools: `end_call()`, `log_complaint()`, `reschedule_call()`

- **`web/server.py`**: Flask web server
  - `/api/initiate-call`: Endpoint to start new calls
  - `/api/transcripts`: Lists all call transcripts
  - `/api/analyze/<filename>`: Analyzes a specific transcript
  - `/api/analysis-summary`: Provides aggregate statistics

- **`analyzer.py`**: Conversation analysis engine
  - `ConversationAnalyzer` class: Uses Gemini to analyze call quality
  - Generates insights: sentiment, predictions, recommendations
  - Saves predictions to `predictions/` folder

### Directories

- **`logs/`**: Stores raw conversation transcripts (JSON format)
- **`predictions/`**: Stores AI-generated analysis results
- **`web/`**: Contains web server and frontend files
- **`KMS/`**: Key management (if applicable)

### Configuration Files

- **`.env.local`**: Environment variables (API keys, credentials)
- **`outbound-trunk.json`**: SIP trunk configuration
- **`requirements.txt`**: Python dependencies

---

## 🔧 Troubleshooting

### Common Issues

**1. SIP 403 Forbidden Error**
- **Cause**: SIP trunk not configured correctly or insufficient permissions
- **Solution**: 
  - Verify your SIP trunk credentials in `outbound-trunk.json`
  - Ensure your SIP provider allows calls to the destination country
  - Check that `SIP_OUTBOUND_TRUNK_ID` in `.env.local` is correct

**2. Agent Not Joining Calls**
- **Cause**: Agent worker not running or connection issues
- **Solution**:
  - Ensure `python agent.py dev` is running in a separate terminal
  - Verify `LIVEKIT_URL` matches between `.env.local` and web server
  - Check LiveKit dashboard for active agents

**3. "Command timeout" in Web UI**
- **Cause**: LiveKit CLI not accessible or `call_lk.bat` missing
- **Solution**:
  - Verify LiveKit CLI is installed: `lk --version`
  - Check that `web/call_lk.bat` exists and is executable
  - Ensure environment variables are loaded correctly

**4. Missing API Keys**
- **Cause**: `.env.local` not configured or keys invalid
- **Solution**:
  - Verify all required keys are present in `.env.local`
  - Test each API key individually
  - Check for typos or extra spaces in the file

**5. Analysis Fails**
- **Cause**: Gemini API rate limits or invalid transcript format
- **Solution**:
  - Check `GEMINI_API_KEY` is valid
  - Ensure transcript JSON files are properly formatted
  - Review logs for specific error messages

---

## 📊 Understanding the Flow

1. **Call Initiation**: User triggers a call via Web UI or CLI
2. **Dispatch**: LiveKit creates a new room and dials the phone number via SIP trunk
3. **Agent Connection**: When call is answered, the agent worker joins the room
4. **Conversation**: 
   - User speaks → Deepgram (STT) → Text
   - Text → Google Gemini (LLM) → Response
   - Response → Cartesia (TTS) → Audio → User hears
5. **Transcript Saving**: Full conversation saved to `logs/transcript_*.json`
6. **Analysis**: Analyzer processes transcript and generates insights
7. **Results**: Analysis saved to `predictions/prediction_*.json`

---

**Built with ❤️ using LiveKit, Google Gemini, Deepgram, and Cartesia**
