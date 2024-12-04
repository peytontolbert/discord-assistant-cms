import threading
import time
from chatgpt.text import TextManager
from fivetts.tts_service import F5TTSService
from ears.whisper_manager import WhisperManager
from collections import deque
import soundfile as sf
import numpy as np
import sounddevice as sd
import logging
import scipy.signal
import os
from .conversation_logger import ConversationLogger

class ConversationManager:
    def __init__(self, openai_api_key, audio_config=None):
        self.text_manager = TextManager(openai_api_key)
        self.speech_manager = F5TTSService()
        
        # Validate audio configuration
        if not audio_config:
            raise ValueError("Audio configuration required")
        
        # Store audio config
        self.input_device = audio_config['input_device']  # CABLE Output (where Discord audio comes out)
        self.output_device = audio_config['output_device']  # CABLE Input (where TTS will go in)
        self.sample_rate = audio_config['sample_rate']
        
        # Initialize whisper to listen to Discord's audio output
        self.whisper = WhisperManager(
            threshold=0.03,
            input_device=self.input_device  # Listen to CABLE Output where Discord audio comes out
        )
        
        self.conversation_history = deque(maxlen=5)
        self.stop_event = threading.Event()
        self.system_prompt = "You are a helpful assistant."
        
        # Audio configuration
        self.channels = 1
        self.chunk_duration = 0.5
        self.chunk_size = int(self.sample_rate * self.chunk_duration)
        self.audio_format = np.float32
        
        # Stream configuration
        self.stream_config = {
            'channels': self.channels,
            'samplerate': self.sample_rate,
            'blocksize': self.chunk_size,
            'dtype': self.audio_format
        }
        
        self.is_speaking = False
        self.last_speech_time = 0
        self.last_speech_duration = 0
        self.logger = ConversationLogger()

    def set_system_prompt(self, prompt):
        """Allow user to set the system prompt for the conversation"""
        self.system_prompt = prompt
        self.logger.set_system_prompt(prompt)
        print(f"System prompt updated to: {prompt}")

    def transcribe_audio_stream(self):
        """Continuously check for and process transcriptions"""
        try:
            while not self.stop_event.is_set():
                try:
                    # Check if we're currently speaking or recently finished
                    current_time = time.time()
                    if hasattr(self, 'is_speaking') and self.is_speaking:
                        time.sleep(0.1)
                        continue
                    
                    if hasattr(self, 'last_speech_time') and hasattr(self, 'last_speech_duration'):
                        time_since_speech = current_time - self.last_speech_time
                        if time_since_speech < self.last_speech_duration:
                            time.sleep(0.1)
                            continue

                    # Get transcription from whisper queue
                    transcription = self.whisper.get_transcription()
                    
                    # Only process if we got a valid transcription and we're not speaking
                    if (transcription and 
                        transcription.strip() and 
                        transcription not in ["No speech detected.", "Transcription failed."] and
                        not getattr(self, 'is_speaking', False)):
                        
                        # Get the audio file path from whisper
                        user_audio_path = self.whisper.last_audio_file
                        
                        logging.info(f"User said: {transcription}")
                        
                        # Add to conversation history
                        self.conversation_history.append({
                            "role": "user", 
                            "content": transcription
                        })
                        
                        # Generate and speak response
                        self.generate_response(transcription)
                        
                        # Log the interaction after response is generated
                        if hasattr(self, 'last_assistant_audio'):
                            self.logger.log_interaction(
                                user_audio_path=user_audio_path,
                                assistant_audio_path=self.last_assistant_audio,
                                user_text=transcription,
                                assistant_text=self.conversation_history[-1]["content"],
                                conversation_history=list(self.conversation_history)
                            )
                    
                    time.sleep(0.1)
                        
                except Exception as e:
                    logging.error(f"Error in transcription loop: {e}", exc_info=True)
                    time.sleep(1)
                    continue
                    
        except Exception as e:
            logging.error(f"Fatal error in transcription stream: {e}", exc_info=True)
            self.stop()

    def generate_response(self, user_input):
        """Generate and speak assistant response"""
        try:
            # Get assistant response
            response = self.text_manager.text_to_text(
                system_prompt=self.system_prompt,
                user_prompt=user_input
            )
            print(f"Assistant said: {response.content}")
            # Add response to history
            self.conversation_history.append({"role": "assistant", "content": response.content})
            
            # Convert response to speech using F5TTS in a separate thread
            speech_thread = threading.Thread(
                target=self._generate_and_play_speech,
                args=(response.content,),
                daemon=False
            )
            speech_thread.start()
            
        except Exception as e:
            print(f"Error generating response: {e}")

    def _generate_and_play_speech(self, text):
        """Helper method to generate and play speech to virtual microphone"""
        try:
            self.is_speaking = True
            
            # Generate and play speech
            speech_file = self.speech_manager.synthesize(text)
            if speech_file and os.path.exists(speech_file):
                # Store the speech file path for logging
                self.last_assistant_audio = speech_file
                
                # Read and play the audio
                data, samplerate = sf.read(speech_file)
                
                duration = len(data) / samplerate
                self.last_speech_time = time.time()
                self.last_speech_duration = duration + 2.0
                
                sd.play(data, samplerate, device=self.output_device, blocking=True)
                time.sleep(1.0)
                
            self.is_speaking = False
                
        except Exception as e:
            self.is_speaking = False
            logging.error(f"Error in speech generation/playback: {e}")

    def play_audio_file(self, file_path):
        """Play audio file through default output device"""
        try:
            # Read the WAV file
            data, samplerate = sf.read(file_path)
            
            # Convert to float32 if needed
            if data.dtype != np.float32:
                data = data.astype(np.float32)
            
            # If stereo, convert to mono
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)

            # Normalize audio to prevent clipping
            data = data / np.max(np.abs(data))

            # Play audio with blocking=True to ensure completion
            try:
                sd.play(data, samplerate, blocking=True)
            except Exception as e:
                logging.error(f"Error during playback: {e}")
                
        except Exception as e:
            logging.error(f"Error playing audio: {e}")

    def stop(self):
        """Stop the conversation manager"""
        self.stop_event.set()
        self.logger.end_session()  # End logging session
        if hasattr(self, 'whisper'):
            self.whisper.stop_listening()
        if hasattr(self, 'speech_manager'):
            self.speech_manager.cleanup()

    def start(self):
        """Start the conversation manager"""
        self.stop_event.clear()
        self.logger.start_session()  # Start new logging session
        
        try:
            # Start the whisper listening stream
            success = self.whisper.start_listening(
                sample_rate=self.sample_rate,
                channels=2  # Match Discord's stereo output
            )
            
            if not success:
                raise RuntimeError("Failed to start Whisper listening stream")
            
            # Create non-daemon thread before starting it
            transcription_thread = threading.Thread(
                target=self.transcribe_audio_stream,
                daemon=False  # Set daemon status before starting
            )
            transcription_thread.start()
            
            return transcription_thread
            
        except Exception as e:
            logging.error(f"Failed to start conversation: {e}")
            self.stop()
            raise