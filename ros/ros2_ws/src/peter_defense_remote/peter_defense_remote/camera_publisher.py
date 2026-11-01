"""Probe real frames before selecting a Linux camera backend."""
import re
import subprocess
import time

import cv2
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage


class CameraPublisher(Node):
    def __init__(self):
        super().__init__('peter_remote_camera')
        self.declare_parameter('device', '/dev/video0')
        self.declare_parameter('jpeg_quality', 90)
        self.device = self.get_parameter('device').value
        quality = self.get_parameter('jpeg_quality').value
        if not 1 <= quality <= 100:
            raise ValueError('jpeg_quality must be between 1 and 100')
        self.quality = quality
        self.capture = None
        self.configure_auto_controls()
        self.capture = self.open_camera()
        self.publisher = self.create_publisher(
            CompressedImage, '/peter/remote/video/compressed', qos_profile_sensor_data)
        self.failures = 0
        self.timer = self.create_timer(1.0 / 30.0, self.publish_frame)

    def control(self, *args):
        result = subprocess.run(
            ['v4l2-ctl', '--device', self.device, *args],
            capture_output=True, text=True, timeout=5, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return result.stdout

    def configure_auto_controls(self):
        controls = self.control('--list-ctrls-menus')
        # Drivers use either exposure_auto or auto_exposure. Prefer full auto,
        # then aperture priority (automatic shutter on fixed-aperture webcams).
        blocks = re.split(r'(?=^\s*\w+\s+0x[0-9a-f]+)', controls, flags=re.M)
        exposure = False
        for block in blocks:
            match = re.match(r'\s*(exposure_auto|auto_exposure)\s+0x', block)
            if not match:
                continue
            menu = re.findall(r'^\s*(\d+):\s*(.+)$', block, re.M)
            modes = {label.strip().lower(): value for value, label in menu}
            choice = modes.get('auto mode') or modes.get('auto')
            if choice is None:
                choice = modes.get('aperture priority mode') or modes.get('aperture priority')
            if choice is not None:
                self.control(f'--set-ctrl={match[1]}={choice}')
                exposure = True
                self.get_logger().info(f'Enabled automatic exposure: {match[1]}={choice}')
        if not exposure:
            raise RuntimeError('Camera exposes no supported automatic exposure mode:\n' + controls)
        gain = re.search(r'^\s*(autogain|gain_automatic|auto_gain)\s+0x', controls, re.M)
        if gain:
            self.control(f'--set-ctrl={gain[1]}=1')
            self.get_logger().info('Enabled automatic gain')
        else:
            self.get_logger().warning(
                'No independent automatic gain control is exposed. Gain may be managed '
                'by camera auto exposure; independent auto gain cannot be verified.')
        # Do not let exposure silently lower the requested frame rate.
        if re.search(r'^\s*exposure_auto_priority\s+0x', controls, re.M):
            self.control('--set-ctrl=exposure_auto_priority=0')

    def open_camera(self):
        if not re.fullmatch(r'/dev/video\d+', self.device):
            raise ValueError('device must be a /dev/videoN path')
        candidates = [('V4L2 MJPEG', self.device, cv2.CAP_V4L2, 'MJPG'),
                      ('V4L2 YUYV', self.device, cv2.CAP_V4L2, 'YUYV')]
        for caps, decode in [
            ('image/jpeg,width=3840,height=2160,framerate=30/1', 'jpegdec ! '),
            ('video/x-raw,width=3840,height=2160,framerate=30/1', ''),
        ]:
            pipeline = (f'v4l2src device={self.device} ! {caps} ! {decode}'
                        'videoconvert ! video/x-raw,format=BGR ! '
                        'appsink drop=true max-buffers=1 sync=false')
            candidates.append(('GStreamer ' + caps.split(',')[0], pipeline,
                               cv2.CAP_GSTREAMER, None))
        errors = []
        for label, source, backend, fourcc in candidates:
            cap = None
            try:
                cap = cv2.VideoCapture(source, backend)
                if not cap.isOpened():
                    raise RuntimeError('could not open')
                if fourcc:
                    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2160)
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                # Validate decoded frames, negotiated rate, and actual delivery.
                for _ in range(5):
                    ok, frame = cap.read()
                    if not ok or frame is None or frame.shape[:2] != (2160, 3840):
                        raise RuntimeError('did not deliver a 3840x2160 frame')
                fps = cap.get(cv2.CAP_PROP_FPS)
                if abs(fps - 30) > 0.5:
                    raise RuntimeError(f'negotiated {fps:.2f} FPS instead of 30')
                start = time.monotonic()
                for _ in range(30):
                    ok, frame = cap.read()
                    if not ok or frame is None or frame.shape[:2] != (2160, 3840):
                        raise RuntimeError('frame validation failed during rate probe')
                measured = 30 / (time.monotonic() - start)
                if measured < 28.5:
                    raise RuntimeError(f'measured only {measured:.1f} FPS')
                self.get_logger().info(
                    f'Selected {label}: 3840x2160, negotiated {fps:.2f} FPS, '
                    f'probe {measured:.1f} FPS')
                return cap
            except (RuntimeError, cv2.error) as exc:
                errors.append(f'{label}: {exc}')
                self.get_logger().warning(errors[-1])
                if cap is not None:
                    cap.release()
        raise RuntimeError('No backend passed 4K/30 validation:\n' + '\n'.join(errors))

    def publish_frame(self):
        ok, frame = self.capture.read()
        if not ok or frame is None or frame.shape[:2] != (2160, 3840):
            self.failures += 1
            self.get_logger().error('Camera read failed or resolution changed')
            if self.failures >= 30:
                raise RuntimeError('Camera failed 30 consecutive reads; restart the node')
            return
        self.failures = 0
        stamp = self.get_clock().now().to_msg()
        ok, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
        if not ok:
            raise RuntimeError('JPEG encoding failed')
        message = CompressedImage()
        message.header.stamp = stamp
        message.header.frame_id = 'peter_remote_camera_optical_frame'
        message.format = 'bgr8; jpeg compressed bgr8'
        message.data = jpeg.tobytes()
        self.publisher.publish(message)

    def destroy_node(self):
        if self.capture is not None:
            self.capture.release()
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = CameraPublisher()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
