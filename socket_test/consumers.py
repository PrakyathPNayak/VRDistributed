import base64
import json
import cv2
import numpy as np
import asyncio
import logging
import struct
import time
import os
import platform
from channels.generic.websocket import AsyncWebsocketConsumer
from typing import Optional
from queue import Queue
from threading import Thread, Event

from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA

logger = logging.getLogger(__name__)

class StreamingConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = False
        self.cap: Optional[cv2.VideoCapture] = None
        self.aes_key: Optional[bytes] = None
        self.iv: Optional[bytes] = None
        self.stream_task: Optional[asyncio.Task] = None
        self.frame_queue = Queue(maxsize=3)
        self.capture_thread: Optional[Thread] = None
        self.capture_ready = Event()  # Added to signal when capture is ready
        self.frame_width = 1920
        self.frame_height = 1080
        self.fps = 60
        self.jpeg_quality = 20
        self.sequence_number = 0

        try:
            with open("server_public.pem", "rb") as f:
                self.pub_key = RSA.import_key(f.read())
            with open("server_private.pem", "rb") as f:
                self.priv_key = RSA.import_key(f.read())
            logger.info("RSA keys loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load RSA keys: {e}")
            self.pub_key = None
            self.priv_key = None

    def capture_frames(self):
        logger.info("Capture thread started")
        # Signal that capture thread is ready
        self.capture_ready.set()
        
        while self.running and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()
                if ret:
                    if not self.frame_queue.full():
                        self.frame_queue.put(frame)
                    else:
                        # Remove oldest frame and add new one
                        try:
                            self.frame_queue.get_nowait()  # Remove old frame
                        except:
                            pass
                        self.frame_queue.put(frame)
                        logger.warning("Frame queue was full, replaced oldest frame")
                else:
                    logger.error("Failed to capture frame")
                    break
            except Exception as e:
                logger.error(f"Error in capture_frames: {e}")
                break
                
        logger.info("Capture thread ended")

    async def connect(self):
        await self.accept()
        if not self.pub_key or not self.priv_key:
            await self._send_error("RSA keys not available")
            await self.close()
            return

        pub_key_b64 = base64.b64encode(self.pub_key.export_key()).decode()
        await self.send(text_data=json.dumps({
            'type': 'rsa_public_key',
            'key': pub_key_b64
        }))

    async def disconnect(self, close_code):
        await self._cleanup()

    async def _initialize_camera(self) -> bool:
        try:
            backends = [
                cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_V4L2,
                cv2.CAP_ANY
            ]

            for backend in backends:
                self.cap = cv2.VideoCapture(0, backend)
                if self.cap.isOpened():
                    break

            if not self.cap or not self.cap.isOpened():
                logger.error("Failed to open camera")
                return False

            # Set camera properties
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            
            # Add buffer size setting to reduce latency
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Test frame capture
            ret, test_frame = self.cap.read()
            if not ret:
                logger.error("Failed to capture test frame")
                return False

            # Start capture thread
            self.capture_ready.clear()
            self.running = True  # Set running to True before starting thread
            self.capture_thread = Thread(target=self.capture_frames, daemon=True)
            self.capture_thread.start()
            
            # Wait for capture thread to be ready (with timeout)
            if not self.capture_ready.wait(timeout=5.0):
                logger.error("Capture thread failed to start within timeout")
                return False
                
            logger.info(f"Camera initialized: {self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)} @ {self.cap.get(cv2.CAP_PROP_FPS)}fps")
            return True
            
        except Exception as e:
            logger.error(f"Camera init failed: {e}")
            return False

    async def _stream_video(self):
        logger.info("Stream video started")
        try:
            await asyncio.sleep(0.1)

            while self.running and self.cap and self.cap.isOpened():
                if self.frame_queue.empty():
                    await asyncio.sleep(0.01)
                    continue

                try:
                    frame = self.frame_queue.get_nowait()
                except Exception as e:
                    logger.debug(f"Queue exception: {e}")
                    await asyncio.sleep(0.01)
                    continue

                ret, buffer = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
                if not ret:
                    logger.warning("Failed to encode frame")
                    continue

                jpeg_data = buffer.tobytes()

                nonce = os.urandom(12)

                try:
                    cipher = AES.new(self.aes_key, AES.MODE_GCM, nonce=nonce)
                    ciphertext, tag = cipher.encrypt_and_digest(jpeg_data)
                except Exception as e:
                    logger.error(f"Encryption error: {e}")
                    continue


                timestamp = time.time()
                total_encrypted_size = len(nonce) + len(ciphertext) + len(tag)
                header = struct.pack("dII", timestamp, self.sequence_number, total_encrypted_size)
                frame_data = header + nonce + ciphertext + tag

                try:
                    await self.send(bytes_data=frame_data)
                except Exception as e:
                    logger.error(f"Send error: {e}")

                self.sequence_number += 1

        except Exception as e:
            logger.error(f"Stream error: {e}")
            import traceback
            logger.error(traceback.format_exc())
        finally:
            logger.info("Stream video ended")
            await self._cleanup()


    async def _send_error(self, message: str):
        await self.send(text_data=json.dumps({'type': 'error', 'message': message}))

    async def _cleanup(self):
        logger.info("Starting cleanup")
        self.running = False
        
        if self.stream_task and not self.stream_task.done():
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass

        if self.capture_thread and self.capture_thread.is_alive():
            logger.info("Waiting for capture thread to finish")
            self.capture_thread.join(timeout=2.0)
            if self.capture_thread.is_alive():
                logger.warning("Capture thread did not finish within timeout")

        if self.cap:
            self.cap.release()
            self.cap = None
            
        # Clear the frame queue
        while not self.frame_queue.empty():
            try:
                self.frame_queue.get_nowait()
            except:
                break
                
        logger.info("Cleanup completed")

    async def receive(self, text_data=None, bytes_data=None):
        try:
            if text_data:
                data = json.loads(text_data)
                msg_type = data.get('type')

                if msg_type == 'aes_key_exchange':
                    logger.info("Received AES key exchange")
                    logger.debug(f"Encrypted key (b64): {data['encrypted_key']}")
                    logger.debug(f"IV (b64): {data['iv']}")

                    enc_key = base64.b64decode(data['encrypted_key'])
                    iv = base64.b64decode(data['iv'])
                    cipher = PKCS1_v1_5.new(self.priv_key)
                    decrypted_key_b64 = cipher.decrypt(enc_key, None)

                    if decrypted_key_b64 is None:
                        await self._send_error("Failed to decrypt AES key")
                        return

                    try:
                        decrypted_key = base64.b64decode(decrypted_key_b64)
                    except Exception as e:
                        logger.error("Base64 decode error on decrypted key: %s", e)
                        await self._send_error("Invalid decrypted AES key format")
                        return

                    logger.debug(f"Decrypted AES key (hex): {decrypted_key.hex()}")

                    if len(decrypted_key) > 32:
                        self.aes_key = decrypted_key[:32]
                    elif len(decrypted_key) in [16, 24, 32]:
                        self.aes_key = decrypted_key
                    else:
                        self.aes_key = decrypted_key.ljust(32, b'\x00')

                    self.iv = iv
                    logger.debug(f"Final AES key (hex): {self.aes_key.hex()}")
                    logger.debug(f"Client IV (hex): {iv.hex()}")

                    if await self._initialize_camera():
                        self.stream_task = asyncio.create_task(self._stream_video())
                        await self.send(text_data=json.dumps({
                            'type': 'stream_ready',
                            'message': 'Video stream started'
                        }))
                    else:
                        await self._send_error("Failed to initialize camera")

        except Exception as e:
            logger.error(f"Receive error: {e}")
            await self._send_error(f"Internal error: {str(e)}")
