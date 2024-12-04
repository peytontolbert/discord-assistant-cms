from ears.whisper_manager import WhisperManager
from chatgpt.text import TextManager
from fivetts.tts_service import F5TTSService
import pyaudio
import wave
import threading
import time
import sounddevice as sd
import numpy as np

class VoiceLoop:
    def __init__(self):
        self.whisper = WhisperManager()
        self.text = TextManager()
        self.tts = F5TTSService()
        
        # Audio recording parameters
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paFloat32
        self.CHANNELS = 1
        self.RATE = 16000
        self.RECORD_SECONDS = 5
        self.is_recording = False
        
        # Initialize PyAudio
        self.p = pyaudio.PyAudio()
        
    def record_audio(self):
        stream = self.p.open(format=self.FORMAT,
                           channels=self.CHANNELS,
                           rate=self.RATE,
                           input=True,
                           frames_per_buffer=self.CHUNK)
        
        frames = []
        print("Recording...")
        
        while self.is_recording:
            data = stream.read(self.CHUNK)
            frames.append(np.frombuffer(data, dtype=np.float32))
            
        print("Stopped recording.")
        
        stream.stop_stream()
        stream.close()
        
        # Convert frames to numpy array
        audio_data = np.concatenate(frames)
        return {"array": audio_data, "sampling_rate": self.RATE}
    
    def play_audio(self, audio_data):
        sd.play(audio_data, self.RATE)
        sd.wait()
    
    def start_conversation(self):
        print("Press Enter to start recording, and Enter again to stop.")
        while True:
            input()  # Wait for Enter to start recording
            self.is_recording = True
            
            # Start recording in a separate thread
            record_thread = threading.Thread(target=self.record_audio)
            audio_data = record_thread.start()
            
            input()  # Wait for Enter to stop recording
            self.is_recording = False
            record_thread.join()
            
            # Get the recorded audio data
            audio_data = self.record_audio()
            
            # Process the recorded audio
            print("Processing speech to text...")
            text = self.whisper.transcribe_audio(audio_data)
            
            if not text:
                print("No speech detected. Try again.")
                continue
                
            print(f"You said: {text}")
            
            # Generate response
            print("Generating response...")
            response = self.text.generate_response(text)
            print(f"AI response: {response}")
            
            # Convert response to speech
            print("Converting to speech...")
            audio_response = self.tts.generate_audio(response)
            
            # Play the response
            print("Playing response...")
            self.play_audio(audio_response)
    
    def cleanup(self):
        self.p.terminate()

if __name__ == "__main__":
    voice_loop = VoiceLoop()
    try:
        voice_loop.start_conversation()
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        voice_loop.cleanup()


