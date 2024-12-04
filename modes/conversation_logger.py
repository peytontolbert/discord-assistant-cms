import os
import json
import time
import shutil
import logging
from datetime import datetime
from pathlib import Path

class ConversationLogger:
    def __init__(self, base_dir="conversation_logs"):
        """Initialize conversation logger with base directory"""
        self.base_dir = Path(base_dir)
        self.current_session = None
        self.session_data = {}
        self.ensure_directories()
        
    def ensure_directories(self):
        """Create necessary directories if they don't exist"""
        self.base_dir.mkdir(parents=True, exist_ok=True)
        (self.base_dir / "audio").mkdir(exist_ok=True)
        (self.base_dir / "metadata").mkdir(exist_ok=True)
        
    def start_session(self):
        """Start a new conversation session"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_session = timestamp
        self.session_data = {
            "session_id": timestamp,
            "start_time": time.time(),
            "interactions": [],
            "system_prompt": None
        }
        
    def set_system_prompt(self, prompt):
        """Set the system prompt for the current session"""
        if self.session_data:
            self.session_data["system_prompt"] = prompt
            
    def log_interaction(self, user_audio_path, assistant_audio_path, 
                       user_text, assistant_text, conversation_history):
        """Log a single interaction with audio files and text"""
        if not self.current_session:
            self.start_session()
            
        # Create paths for copied audio files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        user_audio_name = f"user_{timestamp}.wav"
        assistant_audio_name = f"assistant_{timestamp}.wav"
        
        # Copy audio files to log directory
        user_audio_dest = self.base_dir / "audio" / user_audio_name
        assistant_audio_dest = self.base_dir / "audio" / assistant_audio_name
        
        try:
            shutil.copy2(user_audio_path, user_audio_dest)
            shutil.copy2(assistant_audio_path, assistant_audio_dest)
            
            # Create interaction data
            interaction = {
                "timestamp": timestamp,
                "user_audio": str(user_audio_name),
                "assistant_audio": str(assistant_audio_name),
                "user_text": user_text,
                "assistant_text": assistant_text,
                "conversation_history": [dict(msg) for msg in conversation_history]
            }
            
            self.session_data["interactions"].append(interaction)
            self.save_session()
            
        except Exception as e:
            logging.error(f"Error logging interaction: {e}")
            
    def save_session(self):
        """Save current session data to JSON file"""
        if self.current_session:
            try:
                metadata_path = self.base_dir / "metadata" / f"session_{self.current_session}.json"
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    json.dump(self.session_data, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logging.error(f"Error saving session data: {e}")
                
    def end_session(self):
        """End current session and save final data"""
        if self.current_session:
            self.session_data["end_time"] = time.time()
            self.save_session()
            self.current_session = None
            self.session_data = {} 