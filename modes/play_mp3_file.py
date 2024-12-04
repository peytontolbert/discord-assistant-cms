import os
import sounddevice as sd
import numpy as np
import soundfile as sf

def play_audio_file(file_path, stop_event=None):
    """Play an audio file through the virtual cable in a loop until stopped."""
    try:
        if not os.path.exists(file_path):
            print(f"Audio file not found at: {file_path}")
            return

        print(f"Attempting to play audio file in loop: {file_path}")
        
        # Read the audio file
        data, samplerate = sf.read(file_path)
        print(f"Successfully loaded audio file. Sample rate: {samplerate}")
        
        # Convert to float32 if not already
        if data.dtype != np.float32:
            data = data.astype(np.float32)
        
        # If mono, convert to stereo
        if len(data.shape) == 1:
            data = np.column_stack((data, data))
        elif len(data.shape) > 2:
            data = data[:, :2]
            
        # Find the VB-Cable Input device
        devices = sd.query_devices()
        cable_device = None
        for i, device in enumerate(devices):
            if 'CABLE Input' in device['name'] and device['max_output_channels'] > 0:
                cable_device = i
                print(f"\nFound VB-Cable Input device: {device}")
                break
                
        if cable_device is None:
            print("\nCould not find VB-Cable Input device")
            return
            
        device_info = sd.query_devices(cable_device)
        
        # Loop playback until stopped
        while stop_event is None or not stop_event.is_set():
            with sd.OutputStream(device=cable_device,
                               samplerate=samplerate,
                               channels=min(2, device_info['max_output_channels']),
                               dtype=np.float32) as stream:
                print("Starting playback loop...")
                stream.write(data)
                print("Restarting playback...")
            
    except Exception as e:
        print(f"Error playing audio: {e}")
        import traceback
        traceback.print_exc()