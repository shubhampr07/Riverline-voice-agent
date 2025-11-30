
from __future__ import annotations

import asyncio
import logging
from dotenv import load_dotenv
import json
import os
import re
from typing import Any
from datetime import datetime

from livekit import rtc, api
from livekit.agents import (
    AgentSession,
    Agent,
    JobContext,
    function_tool,
    RunContext,
    get_job_context,
    cli,
    WorkerOptions,
    RoomInputOptions,
)
from livekit.plugins import (
    deepgram,
    cartesia,
    silero,
    noise_cancellation,
    google,
)

# ------------------------
# ENV
# ------------------------
load_dotenv(dotenv_path=".env.local")
logger = logging.getLogger("outbound-caller")
logger.setLevel(logging.INFO)

outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")


# ------------------------
# AGENT
# ------------------------
class OutboundCaller(Agent):
    def __init__(
        self,
        *,
        name: str,
        amount_due: str,
        due_date: str,
        summary: str,
        today: str,
        dial_info: dict[str, Any],
    ):
        super().__init__(
            instructions=f"""
You are Joe, a professional customer service representative from American Express Bank. You're making a courteous follow-up call regarding an outstanding payment.

CUSTOMER CONTEXT:
- Customer Name: {name}
- Outstanding Amount: ${amount_due}
- Original Due Date: {due_date}
- Today's Date: {today}

PREVIOUS INTERACTION SUMMARY:
{summary}

YOUR COMMUNICATION STYLE:
- Be warm, friendly, and empathetic - you're here to help, not pressure
- Speak naturally and conversationally, as if talking to a friend
- Listen actively and acknowledge the customer's concerns
- If the customer is frustrated, apologize sincerely and show understanding
- Keep responses concise and clear - avoid banking jargon
- Maintain a helpful, solution-oriented tone throughout

YOUR OBJECTIVES:
1. Politely remind the customer about the outstanding payment
2. Understand their current situation and any challenges they're facing
3. Offer assistance and find a mutually agreeable solution
4. Document any complaints or requests for follow-up

AVAILABLE ACTIONS:
- log_complaint(reason: str) - Use when customer expresses dissatisfaction or has a complaint
- reschedule_call(date: str) - Use when customer requests a callback on a specific date
- end_call() - Use when the conversation naturally concludes or customer requests to end

CONVERSATION GUIDELINES:
- Start with a friendly greeting and confirm you're speaking with {name}
- Briefly state the purpose of your call
- Ask open-ended questions to understand their situation
- If they can't pay now, ask when they might be able to and offer to schedule a callback
- If they dispute the charge, log a complaint and assure them it will be investigated
- Always thank them for their time before ending the call
- Never be pushy or aggressive - maintain professionalism at all times

Remember: Your goal is to maintain a positive customer relationship while addressing the outstanding payment. Be patient, understanding, and helpful.
"""
        )
        self.participant: rtc.RemoteParticipant | None = None
        self.dial_info = dial_info
        self.transcript_log: list[str] = []

    def set_participant(self, participant: rtc.RemoteParticipant):
        self.participant = participant

    async def hangup(self):
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))

    @function_tool()
    async def end_call(self, ctx: RunContext):
        identity = self.participant.identity if self.participant else "unknown"
        logger.info(f"ending the call for {identity}")

        current_speech = ctx.session.current_speech
        if current_speech:
            await current_speech.wait_for_playout()

        await self.hangup()

    @function_tool()
    async def log_complaint(self, ctx: RunContext, reason: str):
        identity = self.participant.identity if self.participant else "unknown"
        log_entry = f"[Complaint] {identity}: {reason}"
        logger.info(log_entry)
        self.transcript_log.append(log_entry)
        return "I'm sorry to hear that. I've logged your concern."

    @function_tool()
    async def reschedule_call(self, ctx: RunContext, date: str):
        identity = self.participant.identity if self.participant else "unknown"
        log_entry = f"[Reschedule] {identity} requested callback on {date}"
        logger.info(log_entry)
        self.transcript_log.append(log_entry)
        return f"No problem. I’ll mark your preferred call-back date as {date}."


# ------------------------
# ENTRYPOINT
# ------------------------
async def entrypoint(ctx: JobContext):
    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect()

    # ---- SAFE METADATA LOAD ----
    raw_metadata = ctx.job.metadata or ""
    logger.info(f"job metadata (raw): {raw_metadata!r}")
    logger.info(f"job metadata (length): {len(raw_metadata)}")
    
    # Handle empty or invalid metadata
    if not raw_metadata or raw_metadata.strip() in ["{", "}", "{}"]:
        logger.error(f"Empty or invalid metadata received: {raw_metadata!r}")
        logger.info("Expected format: {{\"phone_number\":\"+1234567890\"}}")
        ctx.shutdown()
        return

    try:
        dial_info = json.loads(raw_metadata)
        logger.info(f"Successfully parsed JSON metadata: {dial_info}")
    except json.JSONDecodeError as e:
        # Try to fix common JSON issues (unquoted keys and values)
        logger.warning(f"Initial JSON parse failed: {e}, attempting to fix...")
        try:
            # Remove extra whitespace and normalize
            fixed_metadata = raw_metadata.strip()
            
            # Fix unquoted keys: word: -> "word": (handles multiline with re.MULTILINE)
            fixed_metadata = re.sub(r'(\w+)\s*:', r'"\1":', fixed_metadata)
            
            # Fix unquoted values: :value} or :value, or :value\n
            # This pattern handles values that aren't already quoted
            # Matches everything after : until we hit a comma, closing brace, or newline
            fixed_metadata = re.sub(r':\s*([^",\{\}\[\]\r\n]+)\s*([,\}\r\n])', r': "\1"\2', fixed_metadata)
            
            # Clean up any extra whitespace around quotes that might have been added
            fixed_metadata = re.sub(r'"\s+([^"]+)\s+"', r'"\1"', fixed_metadata)
            
            logger.info(f"Attempting to parse fixed metadata: {fixed_metadata!r}")
            dial_info = json.loads(fixed_metadata)
            logger.info(f"Successfully fixed and parsed malformed JSON: {dial_info}")
        except Exception as fix_error:
            logger.error(f"Failed to parse metadata even after fix attempt")
            logger.error(f"  Original: {raw_metadata!r}")
            logger.error(f"  Error: {e}")
            logger.error(f"  Fix error: {fix_error}")
            ctx.shutdown()
            return

    phone_number = dial_info.get("phone_number")
    if not phone_number:
        logger.error("Missing phone_number in metadata.")
        ctx.shutdown()
        return

    # Use trunk from metadata OR env
    trunk_id = dial_info.get("trunk_id") or outbound_trunk_id
    if not trunk_id:
        logger.error("Missing SIP trunk ID.")
        ctx.shutdown()
        return

    participant_identity = phone_number

    # ---- EXTRACT CUSTOMER DATA FROM METADATA ----
    customer_name = dial_info.get("customer_name", "Alex")
    amount_due = dial_info.get("amount_due", "1000.00")
    due_date = dial_info.get("due_date", "Unknown")
    summary = dial_info.get("summary", "No past conversation")

    # ---- AGENT INSTANCE ----
    agent = OutboundCaller(
        name=customer_name,
        amount_due=amount_due,
        due_date=due_date,
        summary=summary,
        today=datetime.now().strftime("%B %d, %Y"),
        dial_info=dial_info,
    )

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(),
        tts=cartesia.TTS(
            model="sonic-2",
            voice="bf0a246a-8642-498a-9950-80c35e9276b5",
            language="en",
        ),
        llm=google.LLM(
            model="gemini-2.5-flash-lite",
            temperature=0.8,
            api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        ),
    )

    # ---- SAVE TRANSCRIPT AT SHUTDOWN ----
    async def write_transcript():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"logs/transcript_{ctx.room.name}_{ts}.json"
        os.makedirs("logs", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "transcript": session.history.to_dict(),
                    "custom_log": agent.transcript_log,
                },
                f,
                indent=2,
            )
        logger.info(f"Transcript saved to {path}")
        
        # ---- AUTO-ANALYZE AND SAVE PREDICTION ----
        try:
            from analyzer import ConversationAnalyzer
            analyzer = ConversationAnalyzer()
            logger.info("Running conversation analysis...")
            analysis = await analyzer.analyze_transcript_file(path, save_prediction=True)
            if "error" not in analysis:
                logger.info("✅ Analysis completed and prediction saved")
            else:
                logger.warning(f"Analysis failed: {analysis.get('error')}")
        except Exception as e:
            logger.error(f"Failed to run analysis: {e}")

    ctx.add_shutdown_callback(write_transcript)

    # ---- START SESSION ----
    session_task = asyncio.create_task(
        session.start(
            agent=agent,
            room=ctx.room,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVCTelephony()
            ),
        )
    )

    # ---- DIAL USER ----
    try:
        await ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=ctx.room.name,
                sip_trunk_id=trunk_id,
                sip_call_to=phone_number,
                participant_identity=participant_identity,
                wait_until_answered=True,
            )
        )

        await session_task
        participant = await ctx.wait_for_participant(identity=participant_identity)
        logger.info(f"participant joined: {participant.identity}")
        agent.set_participant(participant)

    except api.TwirpError as e:
        logger.error(f"SIP ERROR: {e.message}")
        logger.error(f"SIP Status Code: {e.metadata.get('sip_status_code', 'N/A')}")
        logger.error(f"SIP Status: {e.metadata.get('sip_status', 'N/A')}")
        logger.error(f"Error Code: {e.code}")
        logger.error(f"Full metadata: {e.metadata}")
        logger.error(f"Attempted to call: {phone_number} using trunk: {trunk_id}")
        ctx.shutdown()


# ------------------------
# MAIN
# ------------------------
if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-caller",
        )
    )
