import numpy as np
import struct
import json
import threading
from time import perf_counter, sleep
from multiprocessing import shared_memory
import cv2 as cv
from PIL import Image

class FrameReader:
    """
    Frame reader for Ursina engine to consume frames from shared buffer
    """
    
    def __init__(self, buffer_info_file="buffer_info.json"):
        self.buffer_info_file = buffer_info_file
        self.buffer_info = None
        self.shm = None
        self.last_frame_index = 0
        self.current_frame = None
        self.frame_cache = {}
        
        # Threading for background frame reading
        self.running = False
        self.reader_thread = None
        self.frame_lock = threading.Lock()
        
        # Performance tracking
        self.fps_counter = 0
        self.fps_start_time = perf_counter()
        self.last_fps = 0
        
        self.load_buffer_info()
        self.connect_to_shared_memory()
    
    def load_buffer_info(self):
        """Load buffer information from JSON file"""
        try:
            with open(self.buffer_info_file, 'r') as f:
                self.buffer_info = json.load(f)
            
            print(f"✓ Loaded buffer info:")
            print(f"   Shared memory: {self.buffer_info['shm_name']}")
            print(f"   Dimensions: {self.buffer_info['width']}x{self.buffer_info['height']}x{self.buffer_info['channels']}")
            print(f"   Buffer slots: {self.buffer_info['buffer_size']}")
            
        except Exception as e:
            print(f"❌ Failed to load buffer info: {e}")
            raise
    
    def connect_to_shared_memory(self):
        """Connect to existing shared memory"""
        try:
            self.shm = shared_memory.SharedMemory(
                name=self.buffer_info['shm_name'],
                create=False
            )
            print(f"✓ Connected to shared memory: {self.buffer_info['shm_name']}")
            
        except Exception as e:
            print(f"❌ Failed to connect to shared memory: {e}")
            raise
    
    def read_metadata(self):
        """Read metadata from shared memory"""
        if not self.shm:
            return None
            
        try:
            # Read exactly 64 bytes for metadata
            metadata_size = 64  # Ensure this matches the writer's metadata_size
            metadata_bytes = bytes(self.shm.buf[:metadata_size])
            
            # Use the exact same structure as the writer
            # Q (8 bytes) - frame_index 
            # d (8 bytes) - timestamp
            # I (4 bytes) - width
            # I (4 bytes) - height
            # I (4 bytes) - channels
            # 36x (36 bytes) - padding to reach 64 bytes total
            metadata = struct.unpack('Q d I I I 36x', metadata_bytes)
            
            return {
                'frame_index': metadata[0],
                'timestamp': metadata[1],
                'width': metadata[2],
                'height': metadata[3],
                'channels': metadata[4]
            }
        except Exception as e:
            print(f"❌ Error reading metadata: {e}")
            print(f"   Metadata size: {len(metadata_bytes)} bytes")
            print(f"   Expected: 64 bytes")
            return None
    
    def read_frame(self, frame_index=None):
        """Read a specific frame from shared memory"""
        if not self.shm:
            return None
        
        try:
            # Get current metadata
            metadata = self.read_metadata()
            if not metadata:
                return None
            
            # Use latest frame if no specific index requested
            if frame_index is None:
                frame_index = metadata['frame_index']
            
            # Check if we have a new frame
            if frame_index == self.last_frame_index and self.current_frame is not None:
                return self.current_frame
            
            # Calculate which buffer slot to read from
            # The capture process writes in circular buffer, so we need to find the right slot
            buffer_slot = (frame_index - 1) % self.buffer_info['buffer_size']
            
            # Calculate buffer position
            buffer_offset = self.buffer_info['metadata_size'] + (buffer_slot * self.buffer_info['frame_size'])
            
            # Read frame data
            frame_data = self.shm.buf[buffer_offset:buffer_offset + self.buffer_info['frame_size']]
            
            # Reshape to image
            frame = np.frombuffer(frame_data, dtype=np.uint8).reshape(
                (self.buffer_info['height'], self.buffer_info['width'], self.buffer_info['channels'])
            )
            
            # Make a copy to avoid shared memory issues
            frame = frame.copy()
            
            # Update tracking
            self.last_frame_index = frame_index
            self.current_frame = frame
            
            return frame
            
        except Exception as e:
            print(f"❌ Error reading frame: {e}")
            return None
    
    def get_latest_frame(self):
        """Get the most recent frame available"""
        return self.read_frame()
    
    def get_latest_frame_as_pil(self):
        """Get the latest frame as PIL Image (for Ursina texture)"""
        frame = self.get_latest_frame()
        if frame is not None:
            # Convert BGR to RGB for PIL
            frame_rgb = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            return Image.fromarray(frame_rgb)
        return None
    
    def get_latest_frame_as_texture_data(self):
        """Get the latest frame as texture data (RGB bytes) for Ursina"""
        frame = self.get_latest_frame()
        if frame is not None:
            # Convert BGR to RGB
            frame_rgb = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            return frame_rgb.tobytes()
        return None
    
    def start_background_reader(self):
        """Start background thread for continuous frame reading"""
        if self.running:
            return
        
        self.running = True
        self.reader_thread = threading.Thread(
            target=self._background_reader_loop,
            name="FrameReader"
        )
        self.reader_thread.daemon = True
        self.reader_thread.start()
        print("✓ Started background frame reader")
    
    def _background_reader_loop(self):
        """Background loop for reading frames"""
        while self.running:
            try:
                # Read latest frame
                with self.frame_lock:
                    frame = self.read_frame()
                    if frame is not None:
                        self.fps_counter += 1
                
                # Small delay to prevent excessive CPU usage
                sleep(0.001)  # 1ms
                
            except Exception as e:
                print(f"❌ Background reader error: {e}")
                sleep(0.01)  # Longer delay on error
    
    def stop_background_reader(self):
        """Stop background frame reader"""
        self.running = False
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1.0)
        print("✓ Stopped background frame reader")
    
    def get_frame_safely(self):
        """Thread-safe frame getter"""
        with self.frame_lock:
            return self.current_frame.copy() if self.current_frame is not None else None
    
    def get_frame_as_pil_safely(self):
        """Thread-safe PIL image getter"""
        frame = self.get_frame_safely()
        if frame is not None:
            # Convert BGR to RGB for PIL
            frame_rgb = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
            return Image.fromarray(frame_rgb)
        return None
    
    def calculate_fps(self):
        """Calculate reading FPS"""
        current_time = perf_counter()
        if current_time - self.fps_start_time >= 1.0:
            self.last_fps = self.fps_counter / (current_time - self.fps_start_time)
            self.fps_counter = 0
            self.fps_start_time = current_time
            return self.last_fps
        return None
    
    def get_stats(self):
        """Get performance statistics"""
        metadata = self.read_metadata()
        return {
            'reader_fps': self.last_fps,
            'current_frame_index': metadata['frame_index'] if metadata else 0,
            'last_read_index': self.last_frame_index,
            'frames_behind': (metadata['frame_index'] - self.last_frame_index) if metadata else 0,
            'connected': self.shm is not None
        }
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop_background_reader()
        
        if self.shm:
            try:
                self.shm.close()
                print("✓ Disconnected from shared memory")
            except:
                pass
        
        self.shm = None
        self.current_frame = None

# Example Ursina integration class
class UrsinaScreenTexture:
    """
    Ursina-specific wrapper for screen capture texture updates
    """
    
    def __init__(self, entity, buffer_info_file="buffer_info.json", update_rate=60):
        """
        Initialize screen texture for Ursina entity
        
        Args:
            entity: Ursina entity to apply texture to
            buffer_info_file: Path to buffer info JSON file
            update_rate: Texture update rate in Hz
        """
        from ursina import Texture
        
        self.entity = entity
        self.update_rate = update_rate
        self.update_interval = 1.0 / update_rate
        self.last_update = 0
        
        # Initialize frame reader
        self.frame_reader = FrameReader(buffer_info_file)
        self.frame_reader.start_background_reader()
        
        # Ursina texture
        self.texture = None
        self.texture_name = "screen_capture_texture"
        
        print(f"✓ UrsinaScreenTexture initialized")
        print(f"   Update rate: {update_rate} Hz")
        print(f"   Target entity: {entity}")
    
    def update_texture(self):
        """Update the entity's texture with latest frame"""
        current_time = perf_counter()
        
        # Rate limiting
        if current_time - self.last_update < self.update_interval:
            return False
        
        try:
            # Get latest frame as PIL image
            pil_image = self.frame_reader.get_frame_as_pil_safely()
            
            if pil_image is not None:
                from ursina import Texture
                
                # Create or update texture
                if self.texture is None:
                    self.texture = Texture(pil_image, name=self.texture_name)
                    self.entity.texture = self.texture
                    print(f"✓ Created initial texture: {pil_image.size}")
                else:
                    # Update existing texture
                    self.texture._texture = pil_image
                    self.texture.apply()
                
                self.last_update = current_time
                return True
                
        except Exception as e:
            print(f"❌ Texture update error: {e}")
            return False
        
        return False
    
    def get_performance_stats(self):
        """Get combined performance statistics"""
        reader_stats = self.frame_reader.get_stats()
        reader_stats.update({
            'texture_update_rate': self.update_rate,
            'texture_update_interval': self.update_interval * 1000,  # ms
            'texture_active': self.texture is not None
        })
        return reader_stats
    
    def cleanup(self):
        """Cleanup resources"""
        self.frame_reader.cleanup()
        if self.texture:
            try:
                self.texture.unload()
            except:
                pass
        print("✓ UrsinaScreenTexture cleaned up")

# Standalone example/test function
def test_frame_reader():
    """Test the frame reader independently"""
    print("🧪 Testing Frame Reader...")
    
    try:
        reader = FrameReader()
        reader.start_background_reader()
        
        print("📊 Reading frames for 10 seconds...")
        start_time = perf_counter()
        frame_count = 0
        
        while perf_counter() - start_time < 10.0:
            frame = reader.get_latest_frame()
            if frame is not None:
                frame_count += 1
                
                # Calculate FPS periodically
                fps = reader.calculate_fps()
                if fps is not None:
                    stats = reader.get_stats()
                    print(f"📈 Reader FPS: {fps:6.1f} | "
                          f"Frame #{stats['current_frame_index']:6d} | "
                          f"Behind: {stats['frames_behind']:3d}")
            
            sleep(0.01)  # 100Hz check rate
        
        print(f"✅ Test completed. Read {frame_count} frames")
        
        # Final stats
        final_stats = reader.get_stats()
        print(f"📊 Final stats: {final_stats}")
        
        reader.cleanup()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

# Example Ursina app integration
def create_ursina_example():
    """
    Example of how to integrate with Ursina engine
    """
    example_code = '''
from ursina import *
from ursina_frame_reader import UrsinaScreenTexture

app = Ursina()

# Create a simple quad to display the screen capture
screen_quad = Entity(
    model='cube',
    scale=(16, 9, 0.1),  # 16:9 aspect ratio
    position=(0, 0, 5)
)

# Initialize screen texture
screen_texture = UrsinaScreenTexture(
    entity=screen_quad,
    update_rate=60  # Update texture at 60 FPS
)

# Update function called every frame
def update():
    # Update the screen texture
    screen_texture.update_texture()
    
    # Optional: Display performance stats
    if held_keys['tab']:
        stats = screen_texture.get_performance_stats()
        print(f"FPS: {stats.get('reader_fps', 0):.1f} | "
              f"Frames behind: {stats.get('frames_behind', 0)}")

# Cleanup on exit
def on_exit():
    screen_texture.cleanup()

# Register cleanup
import atexit
atexit.register(on_exit)

# Camera controls
camera.position = (0, 0, -10)
EditorCamera()

app.run()
'''
    
    with open("ursina_screen_capture_example.py", "w") as f:
        f.write(example_code)
    
    print("✓ Created ursina_screen_capture_example.py")
    print("  Run this file after starting the screen capture to see it in action!")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_frame_reader()
    elif len(sys.argv) > 1 and sys.argv[1] == "example":
        create_ursina_example()
    else:
        print("🔗 Frame Reader for Ursina Engine")
        print("Usage:")
        print("  python ursina_frame_reader.py test     - Test frame reading")
        print("  python ursina_frame_reader.py example  - Create Ursina example")
        print("\nOr import this module in your Ursina application:")
        print("  from ursina_frame_reader import UrsinaScreenTexture")
        
        # Quick connection test
        try:
            reader = FrameReader()
            print(f"✅ Successfully connected to shared buffer")
            stats = reader.get_stats()
            print(f"📊 Current stats: {stats}")
            reader.cleanup()
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            print("   Make sure the screen capture script is running first!")