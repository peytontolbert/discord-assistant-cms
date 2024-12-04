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

    def set_system_prompt(self, prompt):
        """Allow user to set the system prompt for the conversation"""
        self.system_prompt = prompt
        print(f"System prompt updated to: {prompt}")

    def transcribe_audio_stream(self):
        """Continuously check for and process transcriptions"""
        try:
            while not self.stop_event.is_set():
                # Get transcription from whisper queue
                transcription = self.whisper.get_transcription()
                
                # Only process if we got a valid transcription
                if (transcription and 
                    transcription.strip() and 
                    transcription not in ["No speech detected.", "Transcription failed."]):
                    
                    logging.info(f"User said: {transcription}")
                    
                    # Add to conversation history
                    self.conversation_history.append({
                        "role": "user", 
                        "content": transcription
                    })
                    
                    # Generate and speak response
                    self.generate_response(transcription)
                else:
                    # Add debug logging for invalid transcriptions
                    if transcription != "No speech detected.":
                        logging.debug(f"Skipped transcription: {transcription}")
                
                # Small sleep to prevent busy waiting
                time.sleep(0.1)
                    
        except Exception as e:
            logging.error(f"Transcription stream error: {e}", exc_info=True)

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
                daemon=True
            )
            speech_thread.start()
            
        except Exception as e:
            print(f"Error generating response: {e}")

    def _generate_and_play_speech(self, text):
        """Helper method to generate and play speech to virtual microphone"""
        try:
            # Generate speech at original quality
            speech_file = self.speech_manager.synthesize(text)
            if not speech_file or not os.path.exists(speech_file):
                logging.error("Failed to generate speech file")
                return

            # Read the WAV file
            data, source_rate = sf.read(speech_file)
            sf.SoundFile(speech_file).close()
            
            # Convert to float32 and mono if needed
            data = data.astype(np.float32)
            if len(data.shape) > 1:
                data = np.mean(data, axis=1)

            # Normalize audio
            max_val = np.max(np.abs(data))
            if max_val > 0:
                data = data / max_val * 0.7

            try:
                # Get device's native sample rate
                device_info = sd.query_devices(self.output_device)
                target_rate = int(device_info['default_samplerate'])
                
                # Resample if needed
                if source_rate != target_rate:
                    ratio = target_rate / source_rate
                    new_length = int(len(data) * ratio)
                    data = scipy.signal.resample(data, new_length)
                
                # Play to CABLE Input using sounddevice's blocking playback
                sd.play(data, target_rate, device=self.output_device, blocking=True)
                # Ensure playback is complete
                sd.wait()
                    
            except Exception as e:
                logging.error(f"Error sending audio to virtual microphone: {e}")
                raise

        except Exception as e:
            logging.error(f"Error in speech generation/virtual mic output: {e}")

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
        if hasattr(self, 'whisper'):
            self.whisper.stop_listening()
        if hasattr(self, 'speech_manager'):
            self.speech_manager.cleanup()

    def start(self):
        """Start the conversation manager"""
        self.stop_event.clear()
        
        try:
            # Start the whisper listening stream - using existing audio setup
            success = self.whisper.start_listening(
                sample_rate=self.sample_rate,
                channels=2  # Match Discord's stereo output
            )
            
            if not success:
                raise RuntimeError("Failed to start Whisper listening stream")
            
            # Start transcription thread
            transcription_thread = threading.Thread(
                target=self.transcribe_audio_stream
            )
            transcription_thread.start()
            
            return transcription_thread
            
        except Exception as e:
            logging.error(f"Failed to start conversation: {e}")
            self.stop()
            raise