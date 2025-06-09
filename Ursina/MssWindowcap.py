import cv2 as cv
import numpy as np
from time import perf_counter, sleep
import mss
import threading
from collections import deque
import ctypes
import gc
import os
import sys
import platform

# Windows-specific imports for non-blocking input
if platform.system() == "Windows":
    import msvcrt
else:
    import select
    import tty
    import termios

# Windows performance optimizations
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Set Windows timer resolution for high precision timing
try:
    winmm = ctypes.windll.winmm
    winmm.timeBeginPeriod(1)  # 1ms timer resolution
    TIMER_SET = True
except:
    TIMER_SET = False

class OptimizedMSSCapture:
    def __init__(self, target_fps=120, monitor_index=1):
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        self.monitor_index = monitor_index
        
        # DON'T initialize MSS here - do it in the capture thread
        self.sct = None
        self.monitor = None
        
        # Ultra-low latency frame buffer
        self.frame_buffer = deque(maxlen=2)
        self.running = False
        self.capture_thread = None
        
        # Performance monitoring
        self.fps_counter = 0
        self.fps_start_time = perf_counter()
        self.last_fps = 0
        
        # Threading optimization
        self.capture_event = threading.Event()
        self.frame_ready = threading.Event()
        
    def init_mss_in_thread(self):
        """Initialize MSS within the capture thread - CRITICAL FIX"""
        try:
            # Create MSS instance in the same thread where it will be used
            self.sct = mss.mss()
            
            # Get monitor configuration
            if self.monitor_index < len(self.sct.monitors):
                self.monitor = self.sct.monitors[self.monitor_index]
                print(f"MSS initialized in capture thread successfully")
                print(f"Available monitors: {len(self.sct.monitors) - 1}")
                print(f"Selected monitor {self.monitor_index}: {self.monitor['width']}x{self.monitor['height']}")
            else:
                # Fallback to primary monitor
                self.monitor = self.sct.monitors[1]
                print(f"Monitor {self.monitor_index} not found, using primary monitor")
                
        except Exception as e:
            print(f"MSS initialization failed in thread: {e}")
            raise
    
    def optimize_process_priority(self):
        """Set high process and thread priority for maximum performance"""
        try:
            if HAS_PSUTIL:
                # Set high process priority
                p = psutil.Process()
                p.nice(psutil.HIGH_PRIORITY_CLASS)
                print("Process priority set to HIGH")
            
            # Set thread priority (Windows specific)
            if hasattr(ctypes, 'windll'):
                kernel32 = ctypes.windll.kernel32
                thread_handle = kernel32.GetCurrentThread()
                kernel32.SetThreadPriority(thread_handle, 2)  # THREAD_PRIORITY_HIGHEST
                print("Thread priority set to HIGHEST")
                
        except Exception as e:
            print(f"Priority optimization failed: {e}")
    
    def capture_loop_optimized(self):
        """Ultra-optimized MSS capture loop - with proper thread-local MSS initialization"""
        # CRITICAL: Initialize MSS in this thread
        try:
            self.init_mss_in_thread()
        except Exception as e:
            print(f"Failed to initialize MSS in capture thread: {e}")
            return
        
        self.optimize_process_priority()
        
        frame_count = 0
        last_time = perf_counter()
        min_sleep_time = 0.0005  # 0.5ms minimum sleep
        
        # Disable garbage collection during capture for consistency
        gc.disable()
        
        try:
            while self.running:
                loop_start = perf_counter()
                
                # Capture frame using MSS (now properly initialized in this thread)
                try:
                    # MSS grab operation
                    sct_img = self.sct.grab(self.monitor)
                    
                    if sct_img is not None:
                        # Convert MSS image to numpy array (BGRA format)
                        frame_bgra = np.array(sct_img)
                        
                        # Convert BGRA to BGR (remove alpha channel)
                        frame_bgr = cv.cvtColor(frame_bgra, cv.COLOR_BGRA2BGR)
                        
                        # Add to buffer (overwrite oldest)
                        if len(self.frame_buffer) >= self.frame_buffer.maxlen:
                            self.frame_buffer.popleft()
                        self.frame_buffer.append(frame_bgr)
                        
                        frame_count += 1
                        
                        # Set frame ready event
                        self.frame_ready.set()
                        
                except Exception as e:
                    print(f"Capture error: {e}")
                    continue
                
                # Precise timing control
                elapsed = perf_counter() - loop_start
                sleep_time = self.frame_time - elapsed
                
                if sleep_time > min_sleep_time:
                    sleep(sleep_time)
                elif sleep_time > 0:
                    # Busy wait for very short delays
                    target_time = loop_start + self.frame_time
                    while perf_counter() < target_time:
                        pass
                
                # Periodic garbage collection
                if frame_count % 1000 == 0:
                    gc.collect()
                    
        finally:
            gc.enable()
            # Cleanup MSS in the same thread
            if self.sct:
                try:
                    self.sct.close()
                except:
                    pass
    
    def start_capture(self):
        """Start optimized capture thread"""
        self.running = True
        self.capture_thread = threading.Thread(
            target=self.capture_loop_optimized,
            name="MSSCapture"
        )
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
        print(f"Started MSS capture thread targeting {self.target_fps} FPS")
    
    def stop_capture(self):
        """Stop capture and cleanup"""
        self.running = False
        
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)
        
        # Reset Windows timer resolution
        if TIMER_SET:
            try:
                winmm.timeEndPeriod(1)
            except:
                pass
        
        print("Capture stopped and cleaned up")
    
    def get_latest_frame(self):
        """Get the most recent frame with minimal latency"""
        if self.frame_buffer:
            return self.frame_buffer[-1]  # Most recent frame
        return None
    
    def calculate_fps(self):
        """Calculate real-time FPS"""
        self.fps_counter += 1
        current_time = perf_counter()
        
        if current_time - self.fps_start_time >= 1.0:
            self.last_fps = self.fps_counter / (current_time - self.fps_start_time)
            self.fps_counter = 0
            self.fps_start_time = current_time
            return self.last_fps
        return None
    
    def get_performance_stats(self):
        """Get detailed performance statistics"""
        return {
            'fps': self.last_fps,
            'buffer_size': len(self.frame_buffer),
            'target_fps': self.target_fps,
            'frame_time_ms': self.frame_time * 1000
        }

def check_for_quit_windows():
    """Windows-compatible non-blocking input check"""
    if msvcrt.kbhit():
        key = msvcrt.getch().decode('utf-8').lower()
        return key in ['q', '\x1b']  # 'q' or Escape
    return False

def check_for_quit_unix():
    """Unix-compatible non-blocking input check"""
    try:
        if select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.read(1).lower()
            return key in ['q', '\x1b']  # 'q' or Escape
    except:
        pass
    return False

def optimize_opencv():
    """Optimize OpenCV for maximum performance"""
    try:
        # Enable optimizations
        cv.setUseOptimized(True)
        cv.setNumThreads(4)  # Use 4 threads for processing
        
        # Check CUDA support
        cuda_devices = cv.cuda.getCudaEnabledDeviceCount()
        if cuda_devices > 0:
            print(f"OpenCV CUDA support available: {cuda_devices} device(s)")
            return True
        else:
            print("OpenCV CUDA not available, using CPU optimizations")
            return False
            
    except Exception as e:
        print(f"OpenCV optimization failed: {e}")
        return False

def main():
    print("=" * 60)
    print("OPTIMIZED MSS SCREEN CAPTURE - TARGET: 120+ FPS")
    print("=" * 60)
    
    # System checks
    print("\n🔧 System Optimization Checks:")
    has_cuda = optimize_opencv()
    print(f"   ✓ OpenCV optimizations enabled")
    print(f"   {'✓' if has_cuda else '✗'} CUDA GPU acceleration")
    print(f"   {'✓' if HAS_PSUTIL else '✗'} Process priority control")
    print(f"   {'✓' if TIMER_SET else '✗'} High-resolution timer")
    print(f"   ✓ Platform: {platform.system()}")
    
    # Get target FPS
    try:
        target_fps = int(input(f"\n🎯 Enter target FPS (default 120): ") or "120")
        showcap = input(f"Show capture window? (y/n, default y): ").strip().lower() in ['y', 'yes', '']
        target_fps = max(60, min(target_fps, 300))  # Clamp between 60-300
    except:
        target_fps = 120
        showcap = True
    
    print(f"\n🚀 Initializing MSS capture at {target_fps} FPS...")
    
    # Choose input checking method based on platform
    if platform.system() == "Windows":
        check_for_quit = check_for_quit_windows
        print("Using Windows-compatible input handling")
    else:
        check_for_quit = check_for_quit_unix
        print("Using Unix-compatible input handling")
    
    try:
        # Create optimized capture instance
        capture = OptimizedMSSCapture(target_fps=target_fps)
        
        # Start capture
        capture.start_capture()
        
        # Setup display with minimal overhead
        window_name = "MSS Optimized Capture"
        if showcap:
            cv.namedWindow(window_name, cv.WINDOW_NORMAL)
            cv.resizeWindow(window_name, 1280, 720)  # Reasonable display size
        
        print(f"\n▶️  Starting capture loop... Press 'Q' to quit")
        print(f"    Target FPS: {target_fps}")
        print(f"    Frame time: {1000/target_fps:.2f}ms")
        print("-" * 50)
        
        # Main display loop
        frame_count = 0
        display_fps_counter = 0
        display_start_time = perf_counter()
        
        while True:
            loop_start = perf_counter()
            
            # Get latest frame
            frame = capture.get_latest_frame()
            
            if frame is not None:
                # Resize for display if needed (optional optimization)
                if frame.shape[0] > 1080:  # Only resize if very large
                    display_frame = cv.resize(frame, (1280, 720), interpolation=cv.INTER_NEAREST)
                else:
                    display_frame = frame
                
                if showcap:
                    # Display frame
                    cv.imshow(window_name, display_frame)
                
                frame_count += 1
                display_fps_counter += 1
                
                # Calculate and display performance stats
                capture_fps = capture.calculate_fps()
                if capture_fps is not None:
                    # Calculate display FPS
                    current_time = perf_counter()
                    if current_time - display_start_time >= 1.0:
                        display_fps = display_fps_counter / (current_time - display_start_time)
                        display_fps_counter = 0
                        display_start_time = current_time
                        
                        # Performance report
                        stats = capture.get_performance_stats()
                        print(f"📊 Capture: {capture_fps:6.1f} FPS | "
                              f"Display: {display_fps:6.1f} FPS | "
                              f"Frames: {frame_count:7d} | "
                              f"Buffer: {stats['buffer_size']}")
            
            # Check for quit - platform-specific
            if showcap:
                key = cv.waitKey(1) & 0xFF
                if key in [ord('q'), ord('Q'), 27]:  # Q or Escape
                    break
            else:
                # Use platform-specific non-blocking input check
                if check_for_quit():
                    break
                
        print(f"\n🏁 Capture completed. Total frames: {frame_count}")
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        try:
            capture.stop_capture()
            cv.destroyAllWindows()
        except:
            pass
        
        print("🧹 Cleanup completed")

if __name__ == "__main__":
    # Performance warning
    print("⚠️  For maximum performance:")
    print("   • Close unnecessary applications")
    print("   • Ensure adequate cooling")
    print("   • Use dedicated GPU if available")
    print("   • Run as administrator for priority boost")
    
    main()
