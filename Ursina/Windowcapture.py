import cv2 as cv
import numpy as np
from time import perf_counter, sleep
import mss
import threading
from collections import deque
import ctypes
import gc
import win32gui
import win32con
import platform
import os

class WindowSpecificMSSCapture:
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
        
    def get_all_windows(self):
        """Get all visible application windows with their positions"""
        windows = []
        
        def enum_window_callback(hwnd, windows_list):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if window_title:
                    try:
                        rect = win32gui.GetWindowRect(hwnd)
                        left, top, right, bottom = rect
                        width = right - left
                        height = bottom - top
                        
                        if width > 100 and height > 100:
                            window_info = {
                                'hwnd': hwnd,
                                'title': window_title,
                                'rect': rect,
                                'region': {
                                    'left': left,
                                    'top': top,
                                    'width': width,
                                    'height': height
                                }
                            }
                            windows_list.append(window_info)
                    except Exception as e:
                        pass
            return True
        
        win32gui.EnumWindows(enum_window_callback, windows)
        return windows
    
    def filter_application_windows(self, windows):
        """Filter to get only main application windows"""
        filtered_windows = []
        
        for window in windows:
            title = window['title']
            
            skip_titles = [
                'Program Manager',
                'Desktop Window Manager',
                'Windows Input Experience',
                'Microsoft Text Input Application',
                'Settings',
                'Task Switching',
                'NVIDIA GeForce Overlay',
                'Task Manager',
                'Capture:',
                'Region:',
                'Switch:'
            ]
            
            if any(skip in title for skip in skip_titles):
                continue
                
            if title in ['', ' ', 'Default IME']:
                continue
                
            try:
                hwnd = window['hwnd']
                style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                if style & win32con.WS_VISIBLE:
                    filtered_windows.append(window)
            except:
                continue
                
        return filtered_windows
    
    def create_window_capture_thread(self, window_info):
        """Create a dedicated capture thread for a specific window"""
        window_title = window_info['title']
        region = window_info['region']
        
        def capture_window_loop():
            sct = mss.mss()
            frame_buffer = deque(maxlen=2)
            fps_counter = 0
            fps_start_time = perf_counter()
            
            print(f"Started capture for: {window_title}")
            print(f"Region: {region['width']}x{region['height']} at ({region['left']}, {region['top']})")
            
            try:
                while self.running:
                    loop_start = perf_counter()
                    
                    try:
                        sct_img = sct.grab(region)
                        
                        if sct_img is not None:
                            frame_bgra = np.array(sct_img)
                            frame_bgr = cv.cvtColor(frame_bgra, cv.COLOR_BGRA2BGR)
                            
                            if len(frame_buffer) >= frame_buffer.maxlen:
                                frame_buffer.popleft()
                            frame_buffer.append(frame_bgr)
                            
                            with self.capture_lock:
                                self.window_captures[window_title] = {
                                    'frame': frame_bgr,
                                    'region': region,
                                    'hwnd': window_info['hwnd'],
                                    'last_update': perf_counter()
                                }
                            
                            fps_counter += 1
                            
                    except Exception as e:
                        print(f"Capture error for {window_title}: {e}")
                        continue
                    
                    current_time = perf_counter()
                    if current_time - fps_start_time >= 1.0:
                        fps = fps_counter / (current_time - fps_start_time)
                        with self.capture_lock:
                            self.fps_counters[window_title] = fps
                        fps_counter = 0
                        fps_start_time = current_time
                    
                    elapsed = perf_counter() - loop_start
                    sleep_time = self.frame_time - elapsed
                    if sleep_time > 0:
                        sleep(sleep_time)
                        
            finally:
                sct.close()
                print(f"Stopped capture for: {window_title}")
        
        return threading.Thread(target=capture_window_loop, name=f"Capture-{window_title}", daemon=True)
    
    def start_all_window_captures(self):
        """Start capturing all application windows"""
        all_windows = self.get_all_windows()
        app_windows = self.filter_application_windows(all_windows)
        
        print(f"\n🔍 Found {len(app_windows)} application windows:")
        for i, window in enumerate(app_windows, 1):
            print(f"   {i}. {window['title']} - {window['region']['width']}x{window['region']['height']}")
        
        if not app_windows:
            print("❌ No application windows found!")
            return
        
        self.running = True
        
        for window_info in app_windows:
            capture_thread = self.create_window_capture_thread(window_info)
            self.capture_threads.append(capture_thread)
            capture_thread.start()
        
        print(f"\n🚀 Started {len(self.capture_threads)} capture threads")
    
    def stop_all_captures(self):
        """Stop all capture threads"""
        self.running = False
        
        for thread in self.capture_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        
        self.capture_threads.clear()
        print("🛑 All captures stopped")
    
    def get_window_frame(self, window_title):
        """Get the latest frame for a specific window - thread-safe"""
        with self.capture_lock:
            if window_title in self.window_captures:
                return self.window_captures[window_title]['frame'].copy()
        return None
    
    def get_all_window_frames(self):
        """Get frames from all captured windows - thread-safe"""
        frames = {}
        with self.capture_lock:
            for title, capture_data in self.window_captures.items():
                frames[title] = capture_data['frame'].copy()
        return frames
    
    def display_all_windows(self):
        """Display all captured windows in separate OpenCV windows"""
        display_windows = {}
        
        try:
            while self.running:
                with self.capture_lock:
                    current_captures = dict(self.window_captures)
                
                for title, capture_data in current_captures.items():
                    frame = capture_data['frame']
                    
                    if frame is not None:
                        if title not in display_windows:
                            window_name = f"Capture: {title[:30]}..."
                            cv.namedWindow(window_name, cv.WINDOW_NORMAL)
                            cv.resizeWindow(window_name, 640, 480)
                            display_windows[title] = window_name
                        
                        cv.imshow(display_windows[title], frame)
                
                key = cv.waitKey(1) & 0xFF
                if key in [ord('q'), ord('Q'), 27]:
                    break
                    
        finally:
            cv.destroyAllWindows()
    
    def get_performance_stats(self):
        """Get performance statistics for all windows - thread-safe"""
        stats = {}
        with self.capture_lock:
            for title, fps in self.fps_counters.items():
                stats[title] = {
                    'fps': fps,
                    'active': title in self.window_captures,
                    'region': self.window_captures[title]['region'] if title in self.window_captures else None
                }
        return stats

class MultiRegionMSSCapture:
    def __init__(self, target_fps=60):
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        
        self.region_captures = {}
        self.capture_lock = threading.RLock()
        self.running = False
        self.capture_threads = []
        
        self.fps_counters = {}
        self.screen_regions = self.create_intelligent_regions()
        
    def create_intelligent_regions(self):
        """Create overlapping regions that cover the entire screen efficiently"""
        sct = mss.mss()
        screen_width = sct.monitors[1]['width']
        screen_height = sct.monitors[1]['height']
        sct.close()
        
        regions = {}
        
        region_width = screen_width // 3
        region_height = screen_height // 3
        overlap = 100
        
        for row in range(3):
            for col in range(3):
                region_name = f"region_{row}_{col}"
                
                left = max(0, col * region_width - overlap)
                top = max(0, row * region_height - overlap)
                width = min(region_width + overlap * 2, screen_width - left)
                height = min(region_height + overlap * 2, screen_height - top)
                
                regions[region_name] = {
                    'left': left,
                    'top': top,
                    'width': width,
                    'height': height
                }
        
        regions['left_half'] = {
            'left': 0, 'top': 0,
            'width': screen_width // 2, 'height': screen_height
        }
        regions['right_half'] = {
            'left': screen_width // 2, 'top': 0,
            'width': screen_width // 2, 'height': screen_height
        }
        regions['center_large'] = {
            'left': screen_width // 4, 'top': screen_height // 4,
            'width': screen_width // 2, 'height': screen_height // 2
        }
        
        print(f"✓ Created {len(regions)} intelligent capture regions")
        return regions
    
    def create_region_capture_thread(self, region_name, region):
        """Create high-performance capture thread for specific region"""
        def region_capture_loop():
            sct = mss.mss()
            fps_counter = 0
            fps_start_time = perf_counter()
            
            print(f"🎯 Started region capture: {region_name} ({region['width']}x{region['height']})")
            
            try:
                while self.running:
                    loop_start = perf_counter()
                    
                    try:
                        sct_img = sct.grab(region)
                        
                        if sct_img is not None:
                            frame_bgra = np.frombuffer(sct_img.bgra, dtype=np.uint8)
                            frame_bgra = frame_bgra.reshape((sct_img.height, sct_img.width, 4))
                            frame_bgr = frame_bgra[:, :, :3]
                            
                            with self.capture_lock:
                                self.region_captures[region_name] = {
                                    'frame': frame_bgr,
                                    'region': region,
                                    'last_update': perf_counter()
                                }
                            
                            fps_counter += 1
                            
                    except Exception as e:
                        print(f"⚠️ Region capture error for {region_name}: {e}")
                        continue
                    
                    current_time = perf_counter()
                    if current_time - fps_start_time >= 1.0:
                        fps = fps_counter / (current_time - fps_start_time)
                        with self.capture_lock:
                            self.fps_counters[region_name] = fps
                        fps_counter = 0
                        fps_start_time = current_time
                    
                    elapsed = perf_counter() - loop_start
                    sleep_time = self.frame_time - elapsed
                    if sleep_time > 0:
                        sleep(sleep_time)
                        
            finally:
                sct.close()
                print(f"🛑 Stopped region capture: {region_name}")
        
        return threading.Thread(target=region_capture_loop, name=f"Region-{region_name}", daemon=True)
    
    def start_all_region_captures(self):
        """Start capturing all screen regions simultaneously"""
        print(f"🚀 Starting {len(self.screen_regions)} region captures...")
        
        self.running = True
        
        for region_name, region in self.screen_regions.items():
            capture_thread = self.create_region_capture_thread(region_name, region)
            self.capture_threads.append(capture_thread)
            capture_thread.start()
        
        print(f"✓ Started {len(self.capture_threads)} region capture threads")
    
    def stop_all_captures(self):
        """Stop all capture threads"""
        self.running = False
        
        for thread in self.capture_threads:
            if thread.is_alive():
                thread.join(timeout=2.0)
        
        self.capture_threads.clear()
        print("🛑 All region captures stopped")
    
    def get_region_frame(self, region_name):
        """Get frame from specific region"""
        with self.capture_lock:
            if region_name in self.region_captures:
                return self.region_captures[region_name]['frame'].copy()
        return None
    
    def get_all_region_frames(self):
        """Get all region frames"""
        frames = {}
        with self.capture_lock:
            for region_name, capture_data in self.region_captures.items():
                frames[region_name] = capture_data['frame'].copy()
        return frames

class RapidWindowSwitchCapture:
    def __init__(self, target_fps=30):
        self.target_fps = target_fps
        self.window_captures = {}
        self.capture_lock = threading.RLock()
        self.running = False
        self.capture_threads = []
        
        # Get current process info to exclude our own windows
        self.current_process_id = os.getpid()
        
    def get_all_windows_fast(self):
        """Fast window enumeration with comprehensive exclusions"""
        windows = []
        
        def enum_callback(hwnd, windows_list):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title and len(title) > 3:
                    try:
                        # Get window process ID to exclude our own windows
                        _, window_process_id = win32gui.GetWindowThreadProcessId(hwnd)
                        
                        # Skip our own process windows
                        if window_process_id == self.current_process_id:
                            return True
                        
                        # Comprehensive exclusion list
                        skip_titles = [
                            'Program Manager',
                            'Desktop Window Manager',
                            'Windows Input Experience',
                            'Microsoft Text Input Application',
                            'Settings',
                            'Task Switching',
                            'NVIDIA GeForce Overlay',
                            'GeForce Experience',
                            'Task Manager',
                            'Registry Editor',
                            'Event Viewer',
                            'Windows Security',
                            'Volume Mixer',
                            'Action center',
                            'Notification area',
                            # Our output windows (extra safety)
                            'Capture:',
                            'Region:',
                            'Switch:',
                            'Rapid Switch Capture',
                            'Waiting for captures',
                            # OpenCV windows
                            'OpenCV',
                            'cv2'
                        ]
                        
                        # Skip based on title content
                        if any(skip_title.lower() in title.lower() for skip_title in skip_titles):
                            return True
                        
                        # Skip very small windows
                        rect = win32gui.GetWindowRect(hwnd)
                        if rect[2] - rect[0] < 300 or rect[3] - rect[1] < 200:
                            return True
                        
                        # Check if window is actually a main application window
                        try:
                            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
                            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
                            
                            # Must have caption and be visible
                            if not (style & win32con.WS_CAPTION) or not (style & win32con.WS_VISIBLE):
                                return True
                            
                            # Skip tool windows
                            if ex_style & win32con.WS_EX_TOOLWINDOW:
                                return True
                                
                        except:
                            return True
                        
                        windows_list.append({
                            'hwnd': hwnd,
                            'title': title,
                            'rect': rect,
                            'process_id': window_process_id
                        })
                        
                    except Exception as e:
                        pass
            return True
        
        win32gui.EnumWindows(enum_callback, windows)
        return windows
    
    def rapid_switch_capture(self):
        """Rapidly switch between windows and capture each - FIXED VERSION"""
        def switch_capture_loop():
            sct = mss.mss()
            original_foreground = None
            successful_captures = 0
            
            print("🔄 Starting rapid window switching capture...")
            print("⚠️ This will briefly switch between windows for capture")
            
            try:
                while self.running:
                    try:
                        # Store original foreground window
                        original_foreground = win32gui.GetForegroundWindow()
                        
                        # Get current windows (excluding our output windows)
                        windows = self.get_all_windows_fast()
                        
                        print(f"📊 Found {len(windows)} windows to capture")
                        
                        if not windows:
                            print("⚠️ No valid windows found for capture")
                            sleep(1.0)
                            continue
                        
                        for i, window in enumerate(windows):
                            if not self.running:
                                break
                                
                            try:
                                print(f"🎯 Capturing window {i+1}/{len(windows)}: {window['title'][:40]}...")
                                
                                # Try to bring window to front
                                win32gui.SetForegroundWindow(window['hwnd'])
                                sleep(0.2)  # Longer pause for better capture
                                
                                # Verify window is actually in foreground
                                current_foreground = win32gui.GetForegroundWindow()
                                if current_foreground == window['hwnd']:
                                    # Capture full screen (showing current window)
                                    screenshot = sct.grab(sct.monitors[1])
                                    frame = np.array(screenshot)
                                    frame_bgr = cv.cvtColor(frame, cv.COLOR_BGRA2BGR)
                                    
                                    # Store capture
                                    with self.capture_lock:
                                        self.window_captures[window['title']] = {
                                            'frame': frame_bgr,
                                            'hwnd': window['hwnd'],
                                            'process_id': window['process_id'],
                                            'last_update': perf_counter()
                                        }
                                    
                                    successful_captures += 1
                                    print(f"✅ Successfully captured: {window['title'][:40]}")
                                else:
                                    print(f"⚠️ Failed to bring to foreground: {window['title'][:40]}")
                                    
                            except Exception as e:
                                print(f"❌ Error capturing {window['title']}: {e}")
                                continue
                        
                        # Restore original foreground window
                        if original_foreground:
                            try:
                                win32gui.SetForegroundWindow(original_foreground)
                                sleep(0.1)
                            except:
                                pass
                        
                        print(f"🎯 Capture cycle complete: {successful_captures}/{len(windows)} successful")
                        
                        # Wait before next cycle
                        sleep(max(1.0, 1.0 / self.target_fps))
                        
                    except Exception as e:
                        print(f"⚠️ Switch capture error: {e}")
                        sleep(1.0)
                        
            finally:
                sct.close()
                print(f"🛑 Rapid switch capture stopped. Total captures: {successful_captures}")
        
        self.running = True
        switch_thread = threading.Thread(target=switch_capture_loop, daemon=True)
        switch_thread.start()
        self.capture_threads.append(switch_thread)
        return switch_thread
    
    def stop_all_captures(self):
        """Stop all capture threads"""
        self.running = False
        
        for thread in self.capture_threads:
            if thread.is_alive():
                thread.join(timeout=3.0)
        
        self.capture_threads.clear()
        print("🛑 All rapid switch captures stopped")
    
    def display_all_windows(self):
        """Display all captured windows - FIXED VERSION"""
        display_windows = {}
        last_update_time = perf_counter()
        
        print("📺 Starting display of captured windows...")
        print("Press 'Q' to quit")
        
        try:
            while self.running:
                current_time = perf_counter()
                
                with self.capture_lock:
                    current_captures = dict(self.window_captures)
                
                if not current_captures:
                    # Show waiting message with timer
                    waiting_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    elapsed = int(current_time - last_update_time)
                    cv.putText(waiting_frame, "Waiting for captures...", 
                              (50, 200), cv.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    cv.putText(waiting_frame, f"Elapsed: {elapsed}s", 
                              (50, 250), cv.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 0), 2)
                    cv.putText(waiting_frame, "Switching between windows...", 
                              (50, 300), cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
                    cv.imshow("Rapid Switch Capture", waiting_frame)
                else:
                    # Close waiting window if it exists
                    try:
                        cv.destroyWindow("Rapid Switch Capture")
                    except:
                        pass
                    
                    # Display captured windows
                    for title, capture_data in current_captures.items():
                        frame = capture_data['frame']
                        
                        if frame is not None:
                            if title not in display_windows:
                                window_name = f"Switch: {title[:30]}..."
                                cv.namedWindow(window_name, cv.WINDOW_NORMAL)
                                cv.resizeWindow(window_name, 640, 480)
                                display_windows[title] = window_name
                                print(f"📺 Displaying: {title}")
                            
                            # Resize frame for display
                            display_frame = cv.resize(frame, (640, 480))
                            
                            # Add timestamp overlay
                            last_update = capture_data.get('last_update', 0)
                            age = current_time - last_update
                            cv.putText(display_frame, f"Age: {age:.1f}s", 
                                      (10, 30), cv.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                            
                            cv.imshow(display_windows[title], display_frame)
                
                key = cv.waitKey(1) & 0xFF
                if key in [ord('q'), ord('Q'), 27]:
                    break
                    
        finally:
            cv.destroyAllWindows()

class EnhancedWindowSpecificMSSCapture(WindowSpecificMSSCapture):
    def __init__(self, target_fps=60):
        super().__init__(target_fps)
        self.backup_regions = self.create_backup_regions()
        
    def create_backup_regions(self):
        """Create backup regions for when windows aren't detected"""
        sct = mss.mss()
        screen_width = sct.monitors[1]['width']
        screen_height = sct.monitors[1]['height']
        sct.close()
        
        return {
            'top_left_quarter': {
                'left': 0, 'top': 0,
                'width': screen_width // 2, 'height': screen_height // 2
            },
            'top_right_quarter': {
                'left': screen_width // 2, 'top': 0,
                'width': screen_width // 2, 'height': screen_height // 2
            },
            'bottom_half': {
                'left': 0, 'top': screen_height // 2,
                'width': screen_width, 'height': screen_height // 2
            },
            'center_window': {
                'left': screen_width // 4, 'top': screen_height // 4,
                'width': screen_width // 2, 'height': screen_height // 2
            }
        }
    
    def start_enhanced_captures(self):
        """Start both window-specific and region-based captures"""
        self.start_all_window_captures()
        
        for region_name, region in self.backup_regions.items():
            window_info = {
                'title': f"Region_{region_name}",
                'hwnd': None,
                'region': region
            }
            capture_thread = self.create_window_capture_thread(window_info)
            self.capture_threads.append(capture_thread)
            capture_thread.start()
        
        print(f"✓ Enhanced capture with {len(self.backup_regions)} backup regions")

def main():
    print("🚀 HIGH-PERFORMANCE MULTI-WINDOW CAPTURE WITHOUT EXTRA MONITORS")
    
    method = input("Choose method (1=Multi-Region, 2=Rapid Switch, 3=Enhanced Window): ")
    
    try:
        if method == "1":
            capture_manager = MultiRegionMSSCapture(target_fps=60)
            capture_manager.start_all_region_captures()
            
            try:
                while capture_manager.running:
                    frames = capture_manager.get_all_region_frames()
                    for region_name, frame in frames.items():
                        if frame is not None:
                            cv.imshow(f"Region: {region_name}", cv.resize(frame, (400, 300)))
                    
                    if cv.waitKey(1) & 0xFF == ord('q'):
                        break
            except KeyboardInterrupt:
                pass
                    
        elif method == "2":
            capture_manager = RapidWindowSwitchCapture(target_fps=5)  # Very low FPS for switching
            capture_manager.rapid_switch_capture()
            
            # Give it time to start capturing
            sleep(2)
            
            capture_manager.display_all_windows()
            
        else:
            capture_manager = EnhancedWindowSpecificMSSCapture(target_fps=30)
            capture_manager.start_enhanced_captures()
            capture_manager.display_all_windows()
        
        capture_manager.stop_all_captures()
        
    except KeyboardInterrupt:
        print("\n⏹️ Interrupted by user")
        try:
            capture_manager.stop_all_captures()
        except:
            pass
    except Exception as e:
        print(f"\n❌ Error: {e}")
        try:
            capture_manager.stop_all_captures()
        except:
            pass

if __name__ == "__main__":
    main()
