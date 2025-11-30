#!/usr/bin/env python3

"""
Conversation Analyzer Module
Analyzes call transcripts to provide insights, predictions, and recommendations
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv(dotenv_path=".env.local")


class ConversationAnalyzer:
    """Analyzes conversation transcripts and provides insights"""
    
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')
    
    async def analyze_transcript(self, transcript_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze a conversation transcript and return comprehensive insights
        
        Args:
            transcript_data: The transcript data from the JSON file
            
        Returns:
            Dictionary containing analysis results
        """
        # Extract conversation items
        items = transcript_data.get("transcript", {}).get("items", [])
        custom_log = transcript_data.get("custom_log", [])
        
        # Build conversation text
        conversation = self._build_conversation_text(items)
        
        # Create analysis prompt
        analysis_prompt = f"""
You are an expert conversation analyst for a customer service call center. Analyze the following phone conversation between a customer service agent (Joe from American Express Bank) and a customer.

CONVERSATION:
{conversation}

CUSTOM LOGS:
{json.dumps(custom_log, indent=2)}

Please provide a comprehensive analysis in the following JSON format:

{{
  "sentiment_analysis": {{
    "overall_sentiment": "positive/neutral/negative",
    "customer_emotion": "calm/frustrated/angry/confused/cooperative",
    "sentiment_score": 0-100,
    "sentiment_trend": "improving/stable/declining",
    "key_emotional_moments": ["moment 1", "moment 2"]
  }},
  "conversation_quality": {{
    "agent_professionalism": 0-100,
    "customer_engagement": 0-100,
    "resolution_likelihood": 0-100,
    "conversation_flow": "smooth/choppy/interrupted",
    "total_turns": 0,
    "average_response_time": "fast/moderate/slow"
  }},
  "key_insights": {{
    "main_topics": ["topic1", "topic2"],
    "customer_intent": "pay/dispute/reschedule/complain/other",
    "payment_commitment": "yes/maybe/no",
    "objections_raised": ["objection1", "objection2"],
    "agent_actions_taken": ["action1", "action2"]
  }},
  "performance_metrics": {{
    "call_outcome": "successful/partial/unsuccessful",
    "agent_effectiveness": 0-100,
    "script_adherence": 0-100,
    "empathy_score": 0-100,
    "problem_solving_score": 0-100
  }},
  "predictions": {{
    "payment_probability": 0-100,
    "callback_needed": true/false,
    "escalation_risk": "low/medium/high",
    "customer_satisfaction": 0-100,
    "churn_risk": "low/medium/high"
  }},
  "recommendations": {{
    "immediate_actions": ["action1", "action2"],
    "follow_up_strategy": "description",
    "agent_coaching_points": ["point1", "point2"],
    "process_improvements": ["improvement1", "improvement2"]
  }},
  "summary": {{
    "one_line_summary": "Brief summary of the call",
    "detailed_summary": "Detailed summary of what happened",
    "next_steps": "What should happen next"
  }}
}}

Provide ONLY the JSON response, no additional text.
"""
        
        # Get analysis from LLM
        try:
            response = await self._get_llm_response(analysis_prompt)
            analysis = self._parse_json_response(response)
            
            # Add metadata
            analysis["metadata"] = {
                "analyzed_at": datetime.now().isoformat(),
                "total_messages": len([item for item in items if item.get("type") == "message"]),
                "conversation_duration": self._calculate_duration(items),
                "interruptions": len([item for item in items if item.get("interrupted", False)]),
                "complaints_logged": len([log for log in custom_log if "[Complaint]" in log]),
                "reschedule_requests": len([log for log in custom_log if "[Reschedule]" in log])
            }
            
            return analysis
            
        except Exception as e:
            return {
                "error": str(e),
                "status": "analysis_failed"
            }
    
    def _build_conversation_text(self, items: List[Dict]) -> str:
        """Build a readable conversation text from transcript items"""
        conversation_lines = []
        
        for item in items:
            if item.get("type") == "message":
                role = item.get("role", "unknown")
                content = " ".join(item.get("content", []))
                speaker = "Agent (Joe)" if role == "assistant" else "Customer"
                
                interrupted = " [INTERRUPTED]" if item.get("interrupted", False) else ""
                conversation_lines.append(f"{speaker}: {content}{interrupted}")
        
        return "\n".join(conversation_lines)
    
    def _calculate_duration(self, items: List[Dict]) -> float:
        """Calculate conversation duration in seconds"""
        timestamps = []
        
        for item in items:
            metrics = item.get("metrics", {})
            if "started_speaking_at" in metrics:
                timestamps.append(metrics["started_speaking_at"])
            if "stopped_speaking_at" in metrics:
                timestamps.append(metrics["stopped_speaking_at"])
        
        if len(timestamps) >= 2:
            return round(max(timestamps) - min(timestamps), 2)
        return 0.0
    
    async def _get_llm_response(self, prompt: str) -> str:
        """Get response from LLM"""
        response = self.model.generate_content(prompt)
        return response.text
    
    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response"""
        # Try to extract JSON from markdown code blocks
        response = response.strip()
        
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            response = response[start:end].strip()
        elif "```" in response:
            start = response.find("```") + 3
            end = response.find("```", start)
            response = response[start:end].strip()
        
        return json.loads(response)
    
    async def analyze_transcript_file(self, file_path: str, save_prediction: bool = True) -> Dict[str, Any]:
        """
        Analyze a transcript file and return insights
        
        Args:
            file_path: Path to the transcript JSON file
            save_prediction: Whether to save the prediction to the predictions folder
            
        Returns:
            Analysis results
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            transcript_data = json.load(f)
        
        analysis = await self.analyze_transcript(transcript_data)
        
        # Save prediction if requested
        if save_prediction and "error" not in analysis:
            self._save_prediction(file_path, analysis)
        
        return analysis
    
    def _save_prediction(self, transcript_path: str, analysis: Dict[str, Any]):
        """Save prediction to the predictions folder"""
        # Create predictions directory if it doesn't exist
        predictions_dir = "predictions"
        os.makedirs(predictions_dir, exist_ok=True)
        
        # Generate prediction filename based on transcript filename
        transcript_filename = os.path.basename(transcript_path)
        prediction_filename = transcript_filename.replace("transcript_", "prediction_")
        prediction_path = os.path.join(predictions_dir, prediction_filename)
        
        # Save the analysis
        with open(prediction_path, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, indent=2)
        
        print(f"✅ Prediction saved to: {prediction_path}")
    
    async def batch_analyze(self, logs_dir: str = "logs") -> List[Dict[str, Any]]:
        """
        Analyze all transcript files in the logs directory
        
        Args:
            logs_dir: Directory containing transcript files
            
        Returns:
            List of analysis results
        """
        results = []
        
        if not os.path.exists(logs_dir):
            return results
        
        for filename in os.listdir(logs_dir):
            if filename.startswith("transcript_") and filename.endswith(".json"):
                file_path = os.path.join(logs_dir, filename)
                try:
                    analysis = await self.analyze_transcript_file(file_path)
                    analysis["source_file"] = filename
                    results.append(analysis)
                except Exception as e:
                    results.append({
                        "source_file": filename,
                        "error": str(e),
                        "status": "failed"
                    })
        
        return results


# CLI for testing
if __name__ == "__main__":
    import asyncio
    import sys
    
    async def main():
        analyzer = ConversationAnalyzer()
        
        if len(sys.argv) > 1:
            # Analyze specific file
            file_path = sys.argv[1]
            print(f"Analyzing {file_path}...")
            analysis = await analyzer.analyze_transcript_file(file_path)
            print(json.dumps(analysis, indent=2))
        else:
            # Analyze all files
            print("Analyzing all transcripts in logs/...")
            results = await analyzer.batch_analyze()
            print(json.dumps(results, indent=2))
    
    asyncio.run(main())
