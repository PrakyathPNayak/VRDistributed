import cv2 as cv
import numpy as np
from time import perf_counter, sleep
import threading
from collections import deque
import ctypes
import gc
import os
import sys
import platform
import win32gui
import win32con
import win32ui
from ctypes import windll

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

class OptimizedWin32WindowCapture:
    def __init__(self, target_fps=120):
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        
        # Ultra-low latency frame buffer
        self.frame_buffer = deque(maxlen=1)  # Minimal buffer for max speed
        self.running = False
        self.capture_thread = None
        
        # Performance monitoring
        self.fps_counter = 0
        self.fps_start_time = perf_counter()
        self.last_fps = 0
        
        # Window tracking
        self.target_hwnd = None
        self.window_title = None
        self.window_rect = None
        
        # Threading optimization
        self.capture_event = threading.Event()
        self.frame_ready = threading.Event()
        
    def find_opera_gx_windows(self):
        """Enhanced Opera GX window detection with multiple patterns"""
        opera_windows = []
        
        def enum_callback(hwnd, windows_list):
            if win32gui.IsWindowVisible(hwnd):
                try:
                    window_title = win32gui.GetWindowText(hwnd)
                    class_name = win32gui.GetClassName(hwnd)
                    
                    if not window_title:
                        return True
                    
                    title_lower = window_title.lower()
                    
                    # Comprehensive Opera GX detection patterns
                    opera_patterns = [
                        'opera',
                        'operagx', 
                        'opera gx',
                        'gx',
                        'browser'
                    ]
                    
                    # Direct title matching
                    is_opera_title = any(pattern in title_lower for pattern in opera_patterns)
                    
                    # Chromium-based detection (Opera GX uses Chromium engine)
                    is_chromium_class = class_name in [
                        'Chrome_WidgetWin_0', 
                        'Chrome_WidgetWin_1',
                        'Chrome_RenderWidgetHostHWND'
                    ]
                    
                    # Additional Opera GX specific checks
                    is_opera_process = False
                    try:
                        _, process_id = win32gui.GetWindowThreadProcessId(hwnd)
                        if HAS_PSUTIL:
                            process = psutil.Process(process_id)
                            process_name = process.name().lower()
                            is_opera_process = 'opera' in process_name or 'gx' in process_name
                    except:
                        pass
                    
                    # Include window if any criteria match
                    if is_opera_title or (is_chromium_class and len(window_title) > 5) or is_opera_process:
                        rect = win32gui.GetWindowRect(hwnd)
                        width = rect[2] - rect[0]
                        height = rect[3] - rect[1]
                        
                        # Filter reasonable window sizes
                        if width > 300 and height > 200:
                            windows_list.append({
                                'hwnd': hwnd,
                                'title': window_title,
                                'class': class_name,
                                'rect': rect,
                                'width': width,
                                'height': height,
                                'process_match': is_opera_process,
                                'title_match': is_opera_title,
                                'class_match': is_chromium_class
                            })
                            
                except Exception as e:
                    pass
            return True
        
        win32gui.EnumWindows(enum_callback, opera_windows)
        
        print(f"🔍 Found {len(opera_windows)} potential Opera GX windows:")
        for i, window in enumerate(opera_windows):
            match_types = []
            if window['title_match']: match_types.append("Title")
            if window['class_match']: match_types.append("Class")
            if window['process_match']: match_types.append("Process")
            
            print(f"   {i+1}. {window['title'][:50]}")
            print(f"      Class: {window['class']} | Size: {window['width']}x{window['height']}")
            print(f"      Matches: {', '.join(match_types) if match_types else 'Heuristic'}")
        
        return opera_windows
    
    def optimize_process_priority(self):
        """Set maximum process and thread priority for ultra performance"""
        try:
            if HAS_PSUTIL:
                p = psutil.Process()
                p.nice(psutil.HIGH_PRIORITY_CLASS)
                print("Process priority set to HIGH")
            
            if hasattr(ctypes, 'windll'):
                kernel32 = ctypes.windll.kernel32
                thread_handle = kernel32.GetCurrentThread()
                kernel32.SetThreadPriority(thread_handle, 2)  # THREAD_PRIORITY_HIGHEST
                print("Thread priority set to HIGHEST")
                
        except Exception as e:
            print(f"Priority optimization failed: {e}")
    
    def capture_window_ultra_fast(self, hwnd):
        """Ultra-optimized Win32 window capture using fastest methods"""
        try:
            # Get window DC
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()
            
            # Get current window dimensions (handle window resizing)
            try:
                current_rect = win32gui.GetWindowRect(hwnd)
                width = current_rect[2] - current_rect[0]
                height = current_rect[3] - current_rect[1]
            except:
                # Use cached dimensions if window query fails
                width = self.window_rect[2] - self.window_rect[0]
                height = self.window_rect[3] - self.window_rect[1]
            
            # Skip if window is minimized or invalid
            if width <= 0 or height <= 0 or win32gui.IsIconic(hwnd):
                return None
            
            # Create bitmap
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)
            
            # Use PrintWindow for background window capture (fastest for Opera GX)
            result = windll.user32.PrintWindow(hwnd, saveDC.GetSafeHdc(), 3)  # PW_RENDERFULLCONTENT
            
            if result:
                # Get bitmap bits directly (ultra-fast conversion)
                bmpinfo = saveBitMap.GetInfo()
                bmpstr = saveBitMap.GetBitmapBits(True)
                
                # Direct numpy conversion without intermediate steps
                img_array = np.frombuffer(bmpstr, dtype=np.uint8)
                img_array = img_array.reshape((height, width, 4))  # BGRA format
                
                # Convert BGRA to BGR by slicing (fastest method)
                frame_bgr = img_array[:, :, :3]  # Drop alpha channel
                
                # Cleanup
                win32gui.DeleteObject(saveBitMap.GetHandle())
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwndDC)
                
                return frame_bgr
            else:
                # Fallback to BitBlt if PrintWindow fails
                saveDC.BitBlt((0, 0), (width, height), mfcDC, (0, 0), win32con.SRCCOPY)
                
                bmpinfo = saveBitMap.GetInfo()
                bmpstr = saveBitMap.GetBitmapBits(True)
                
                img_array = np.frombuffer(bmpstr, dtype=np.uint8)
                img_array = img_array.reshape((height, width, 4))
                frame_bgr = img_array[:, :, :3]
                
                # Cleanup
                win32gui.DeleteObject(saveBitMap.GetHandle())
                saveDC.DeleteDC()
                mfcDC.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwndDC)
                
                return frame_bgr
                
        except Exception as e:
            return None
    
    def capture_loop_ultra_optimized(self):
        """Ultra-optimized capture loop targeting 120+ FPS"""
        if not self.target_hwnd:
            print("No target window set!")
            return
        
        self.optimize_process_priority()
        
        frame_count = 0
        min_sleep_time = 0.0001  # Ultra-minimal sleep
        
        # Disable garbage collection during capture
        gc.disable()
        
        try:
            while self.running:
                loop_start = perf_counter()
                
                # Check if window still exists
                if not win32gui.IsWindow(self.target_hwnd):
                    print(f"Target window no longer exists!")
                    break
                
                # Ultra-fast window capture
                try:
                    frame = self.capture_window_ultra_fast(self.target_hwnd)
                    
                    if frame is not None:
                        # Minimal buffer management (single frame for max speed)
                        if self.frame_buffer:
                            self.frame_buffer.popleft()
                        self.frame_buffer.append(frame)
                        
                        frame_count += 1
                        self.frame_ready.set()
                        
                except Exception as e:
                    continue
                
                # Ultra-precise timing control
                elapsed = perf_counter() - loop_start
                sleep_time = self.frame_time - elapsed
                
                if sleep_time > min_sleep_time:
                    sleep(sleep_time)
                elif sleep_time > 0:
                    # Busy wait for ultra-short delays
                    target_time = loop_start + self.frame_time
                    while perf_counter() < target_time:
                        pass
                
                # Reduced GC frequency for max performance
                if frame_count % 2000 == 0:
                    gc.collect()
                    
        finally:
            gc.enable()
            print(f"Win32 capture stopped. Total frames: {frame_count}")
    
    def start_capture(self, window_title_contains=None):
        """Start optimized capture for Opera GX window"""
        # Find Opera GX windows
        opera_windows = self.find_opera_gx_windows()
        
        if not opera_windows:
            print("❌ No Opera GX windows found!")
            print("Make sure Opera GX is running and visible.")
            return False
        
        # Select target window
        if len(opera_windows) == 1:
            selected_window = opera_windows[0]
            print(f"✅ Auto-selected: {selected_window['title']}")
        else:
            print(f"\n🔍 Multiple Opera GX windows found:")
            for i, window in enumerate(opera_windows):
                print(f"   {i+1}. {window['title'][:60]}")
            
            try:
                if window_title_contains:
                    # Try to find window containing specific text
                    for window in opera_windows:
                        if window_title_contains.lower() in window['title'].lower():
                            selected_window = window
                            print(f"✅ Auto-selected by title match: {selected_window['title']}")
                            break
                    else:
                        choice = int(input("Select window (number): ")) - 1
                        selected_window = opera_windows[choice]
                else:
                    choice = int(input("Select window (number): ")) - 1
                    selected_window = opera_windows[choice]
            except (ValueError, IndexError):
                print("Invalid selection, using first window")
                selected_window = opera_windows[0]
        
        self.target_hwnd = selected_window['hwnd']
        self.window_title = selected_window['title']
        self.window_rect = selected_window['rect']
        
        print(f"\n🎯 Targeting Opera GX window:")
        print(f"   Title: {self.window_title}")
        print(f"   HWND: {hex(self.target_hwnd)}")
        print(f"   Size: {selected_window['width']}x{selected_window['height']}")
        print(f"   Class: {selected_window['class']}")
        
        self.running = True
        self.capture_thread = threading.Thread(
            target=self.capture_loop_ultra_optimized,
            name="Win32OperaCapture"
        )
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
        print(f"🚀 Started Win32 Opera GX capture targeting {self.target_fps} FPS")
        return True
    
    def stop_capture(self):
        """Stop capture and cleanup"""
        self.running = False
        
        if self.capture_thread and self.capture_thread.is_alive():
            self.capture_thread.join(timeout=2.0)
        
        if TIMER_SET:
            try:
                winmm.timeEndPeriod(1)
            except:
                pass
        
        print("Win32 Opera GX capture stopped and cleaned up")
    
    def get_latest_frame(self):
        """Get the most recent frame with minimal latency"""
        if self.frame_buffer:
            return self.frame_buffer[-1]
        return None
    
    def calculate_fps(self):
        """Calculate real-time FPS"""
        self.fps_counter += 1
        current_time = perf_counter()
        
        if current_time - self.fps_start_time >= 0.5:  # Update every 0.5s for responsiveness
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
            'frame_time_ms': self.frame_time * 1000,
            'window_title': self.window_title,
            'hwnd': hex(self.target_hwnd) if self.target_hwnd else None
        }

class MultiOperaGXCapture:
    def __init__(self, target_fps=60):
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        
        # Store window captures with thread-safe access
        self.window_captures = {}
        self.capture_lock = threading.RLock()
        self.running = False
        self.capture_threads = []
        
        # Performance monitoring
        self.fps_counters = {}
        self.frame_counts = {}
        self.start_times = {}
        
    def create_opera_capture_thread(self, window_info):
        """Create capture thread for specific Opera GX window"""
        window_title = window_info['title']
        hwnd = window_info['hwnd']
        
        def capture_opera_loop():
            fps_counter = 0
            fps_start_time = perf_counter()
            
            # Initialize tracking
            self.frame_counts[window_title] = 0
            self.start_times[window_title] = perf_counter()
            
            print(f"🎯 Started Opera GX capture: {window_title[:50]}")
            print(f"   HWND: {hex(hwnd)} | Size: {window_info['width']}x{window_info['height']}")
            
            try:
                while self.running:
                    loop_start = perf_counter()
                    
                    # Check if window still exists
                    if not win32gui.IsWindow(hwnd):
                        print(f"❌ Opera GX window {window_title} no longer exists")
                        break
                    
                    # Create single-use capture instance for this frame
                    temp_capture = OptimizedWin32WindowCapture(self.target_fps)
                    temp_capture.target_hwnd = hwnd
                    temp_capture.window_rect = window_info['rect']
                    
                    # Capture the window
                    frame = temp_capture.capture_window_ultra_fast(hwnd)
                    
                    if frame is not None:
                        # Thread-safe update
                        with self.capture_lock:
                            self.window_captures[window_title] = {
                                'frame': frame,
                                'hwnd': hwnd,
                                'width': frame.shape[1],
                                'height': frame.shape[0],
                                'last_update': perf_counter()
                            }
                        
                        fps_counter += 1
                        self.frame_counts[window_title] += 1
                    
                    # FPS calculation
                    current_time = perf_counter()
                    if current_time - fps_start_time >= 1.0:
                        instant_fps = fps_counter / (current_time - fps_start_time)
                        total_time = current_time - self.start_times[window_title]
                        average_fps = self.frame_counts[window_title] / total_time if total_time > 0 else 0
                        
                        with self.capture_lock:
                            self.fps_counters[window_title] = {
                                'instant_fps': instant_fps,
                                'average_fps': average_fps,
                                'total_frames': self.frame_counts[window_title],
                                'runtime': total_time
                            }
                        
                        fps_counter = 0
                        fps_start_time = current_time
                    
                    # Timing control
                    elapsed = perf_counter() - loop_start
                    sleep_time = self.frame_time - elapsed
                    if sleep_time > 0:
                        sleep(sleep_time)
                        
            except Exception as e:
                print(f"❌ Capture thread error for {window_title}: {e}")
            finally:
                print(f"🛑 Stopped Opera GX capture: {window_title}")
        
        return threading.Thread(target=capture_opera_loop, name=f"OperaGX-{window_title}", daemon=True)
    
    def start_all_opera_captures(self):
        """Start capturing all Opera GX windows"""
        # Find Opera GX windows
        temp_capture = OptimizedWin32WindowCapture()
        opera_windows = temp_capture.find_opera_gx_windows()
        
        if not opera_windows:
            print("❌ No Opera GX windows found!")
            return
        
        print(f"\n🚀 Starting capture for {len(opera_windows)} Opera GX windows...")
        
        self.running = True
        
        for window_info in opera_windows:
            capture_thread = self.create_opera_capture_thread(window_info)
            self.capture_threads.append(capture_thread)
            capture_thread.start()
        
        print(f"✅ Started {len(self.capture_threads)} Opera GX capture threads")
    
    def stop_all_captures(self):
        """Stop all capture threads"""
        self.running = False
        
        for thread in self.capture_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        
        self.capture_threads.clear()
        print("🛑 All Opera GX captures stopped")
    
    def get_window_frame(self, window_title):
        """Get frame from specific Opera GX window"""
        with self.capture_lock:
            if window_title in self.window_captures:
                return self.window_captures[window_title]['frame'].copy()
        return None
    
    def display_all_opera_windows(self):
        """Display all captured Opera GX windows with FPS overlay"""
        display_windows = {}
        
        try:
            while self.running:
                with self.capture_lock:
                    current_captures = dict(self.window_captures)
                
                for title, capture_data in current_captures.items():
                    frame = capture_data['frame']
                    
                    if frame is not None:
                        if title not in display_windows:
                            window_name = f"Opera GX: {title[:35]}..."
                            cv.namedWindow(window_name, cv.WINDOW_NORMAL)
                            cv.resizeWindow(window_name, 800, 600)
                            display_windows[title] = window_name
                        
                        # Add FPS overlay
                        frame_with_fps = self.add_fps_overlay(frame.copy(), title)
                        
                        # Display frame
                        cv.imshow(display_windows[title], frame_with_fps)
                
                key = cv.waitKey(1) & 0xFF
                if key in [ord('q'), ord('Q'), 27]:
                    break
                    
        finally:
            cv.destroyAllWindows()
    
    def add_fps_overlay(self, frame, window_title):
        """Add FPS overlay to frame"""
        if window_title in self.fps_counters:
            fps_data = self.fps_counters[window_title]
            
            instant_fps = fps_data.get('instant_fps', 0)
            avg_fps = fps_data.get('average_fps', 0)
            total_frames = fps_data.get('total_frames', 0)
            runtime = fps_data.get('runtime', 0)
            
            # Create overlay background
            cv.rectangle(frame, (10, 10), (450, 100), (0, 0, 0), -1)
            cv.rectangle(frame, (10, 10), (450, 100), (0, 255, 0), 2)
            
            # Add text
            cv.putText(frame, f"Opera GX FPS: {instant_fps:.1f} | Avg: {avg_fps:.1f}", 
                      (15, 35), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            cv.putText(frame, f"Frames: {total_frames} | Time: {runtime:.1f}s", 
                      (15, 60), cv.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv.putText(frame, f"Win32 API Capture", 
                      (15, 85), cv.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)
        
        return frame

def check_for_quit_windows():
    """Windows-compatible non-blocking input check"""
    if platform.system() == "Windows":
        try:
            import msvcrt
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8').lower()
                return key in ['q', '\x1b']
        except:
            pass
    return False

def optimize_opencv():
    """Optimize OpenCV for maximum performance"""
    try:
        cv.setUseOptimized(True)
        cv.setNumThreads(8)  # Increased for better performance
        
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
    print("=" * 70)
    print("🚀 ULTRA-FAST WIN32 OPERA GX CAPTURE - TARGET: 60-120 FPS")
    print("=" * 70)
    
    # System checks
    print("\n🔧 System Optimization Checks:")
    has_cuda = optimize_opencv()
    print(f"   ✓ OpenCV optimizations enabled")
    print(f"   {'✓' if has_cuda else '✗'} CUDA GPU acceleration")
    print(f"   {'✓' if HAS_PSUTIL else '✗'} Process priority control")
    print(f"   {'✓' if TIMER_SET else '✗'} High-resolution timer")
    print(f"   ✓ Platform: {platform.system()}")
    
    # Choose capture mode
    mode = input("\nChoose capture mode (1=Single Opera GX Window, 2=All Opera GX Windows): ")
    
    try:
        if mode == "1":
            # Single Opera GX window high-performance capture
            target_fps = int(input(f"🎯 Enter target FPS (default 120): ") or "120")
            window_search = input(f"Enter specific Opera GX window title (optional): ").strip()
            showcap = input(f"Show capture window? (y/n, default y): ").strip().lower() in ['y', 'yes', '']
            target_fps = max(60, min(target_fps, 240))
            
            print(f"\n🚀 Initializing single Opera GX Win32 capture at {target_fps} FPS...")
            
            capture = OptimizedWin32WindowCapture(target_fps=target_fps)
            
            if not capture.start_capture(window_search if window_search else None):
                return
            
            window_name = "Opera GX Win32 Capture"
            if showcap:
                cv.namedWindow(window_name, cv.WINDOW_NORMAL)
                cv.resizeWindow(window_name, 1280, 720)
            
            print(f"\n▶️  Starting Opera GX capture loop... Press 'Q' to quit")
            print(f"    Target FPS: {target_fps}")
            print(f"    Frame time: {1000/target_fps:.2f}ms")
            print("-" * 70)
            
            frame_count = 0
            display_fps_counter = 0
            display_start_time = perf_counter()
            
            while True:
                frame = capture.get_latest_frame()
                
                if frame is not None:
                    if showcap:
                        if frame.shape[0] > 1080:
                            display_frame = cv.resize(frame, (1280, 720), interpolation=cv.INTER_NEAREST)
                        else:
                            display_frame = frame
                        
                        cv.imshow(window_name, display_frame)
                    
                    frame_count += 1
                    display_fps_counter += 1
                    
                    capture_fps = capture.calculate_fps()
                    if capture_fps is not None:
                        current_time = perf_counter()
                        if current_time - display_start_time >= 1.0:
                            display_fps = display_fps_counter / (current_time - display_start_time)
                            display_fps_counter = 0
                            display_start_time = current_time
                            
                            stats = capture.get_performance_stats()
                            print(f"📊 Capture: {capture_fps:6.1f} FPS | "
                                  f"Display: {display_fps:6.1f} FPS | "
                                  f"Frames: {frame_count:7d} | "
                                  f"Opera GX: {stats['window_title'][:40]}")
                
                if showcap:
                    key = cv.waitKey(1) & 0xFF
                    if key in [ord('q'), ord('Q'), 27]:
                        break
                else:
                    if check_for_quit_windows():
                        break
            
            print(f"\n🏁 Opera GX capture completed. Total frames: {frame_count}")
            capture.stop_capture()
            
        else:
            # Multi-Opera GX window capture
            target_fps = int(input(f"🎯 Enter target FPS per window (default 60): ") or "60")
            target_fps = max(30, min(target_fps, 120))
            
            print(f"\n🚀 Initializing multi-Opera GX Win32 capture at {target_fps} FPS per window...")
            
            capture_manager = MultiOperaGXCapture(target_fps=target_fps)
            capture_manager.start_all_opera_captures()
            
            if not capture_manager.capture_threads:
                print("❌ No Opera GX capture threads started!")
                return
            
            print(f"\n▶️  Multi-Opera GX capture running... Press 'Q' to quit")
            print("-" * 70)
            
            capture_manager.display_all_opera_windows()
            capture_manager.stop_all_captures()
        
    except KeyboardInterrupt:
        print(f"\n⏹️  Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cv.destroyAllWindows()
        print("🧹 Cleanup completed")

if __name__ == "__main__":
    print("⚠️  For maximum Opera GX capture performance:")
    print("   • Close unnecessary applications")
    print("   • Ensure Opera GX is running")
    print("   • Run as administrator for priority boost")
    print("   • Use dedicated GPU if available")
    
    main()
