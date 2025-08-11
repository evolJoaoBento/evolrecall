"""
Recording controller for managing pause/resume functionality
Replace your openrecall/recording_controller.py with this fixed version
"""

import threading
import time
from datetime import datetime

class RecordingController:
    def __init__(self):
        self.is_recording = True
        self.is_paused = False
        self.pause_event = threading.Event()
        self.pause_event.set()  # Start in recording state (event is set)
        self.stop_event = threading.Event()
        self.session_start_time = datetime.now()
        print("RecordingController initialized: recording=True, paused=False")
        
    def pause(self):
        """Pause the recording"""
        if not self.is_paused:
            self.is_paused = True
            self.is_recording = False
            self.pause_event.clear()  # Clear the event to pause threads
            print("RecordingController: Recording PAUSED")
    
    def resume(self):
        """Resume the recording"""
        if self.is_paused:
            self.is_paused = False
            self.is_recording = True
            self.pause_event.set()  # Set the event to resume threads
            print("RecordingController: Recording RESUMED")
    
    def stop(self):
        """Stop the recording completely"""
        self.is_recording = False
        self.is_paused = False
        self.stop_event.set()
        self.pause_event.set()  # Ensure threads can exit
        print("RecordingController: Recording STOPPED")
    
    def wait_if_paused(self, timeout=None):
        """Call this in your recording loop to respect pause state
        Returns True if should continue, False if should stop"""
        if self.stop_event.is_set():
            return False
            
        # This will block if paused (pause_event is cleared)
        # Will return immediately if not paused (pause_event is set)
        result = self.pause_event.wait(timeout=timeout)
        
        # Check if we should stop
        if self.stop_event.is_set():
            return False
            
        return True
    
    def should_record(self):
        """Simple check if currently recording"""
        return self.is_recording and not self.is_paused and not self.stop_event.is_set()
    
    def get_state(self):
        """Get current recording state"""
        return {
            'is_recording': self.is_recording,
            'is_paused': self.is_paused,
            'session_start_time': self.session_start_time.isoformat()
        }

# Global recording controller instance
recording_controller = RecordingController()