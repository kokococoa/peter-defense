"""Publish camera-native MJPEG frames without decoding or re-encoding them."""
from array import array
import re
import subprocess
import time

import cv2
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage


TARGET_FPS = 20


def jpeg_resolution(data):
    """Read JPEG start-of-frame dimensions without decompressing the image."""
    if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
        raise ValueError('Incomplete JPEG frame')
    offset = 2
    while offset < len(data):
        if data[offset] != 0xFF:
            raise ValueError('Invalid JPEG marker')
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            break
        marker = data[offset]
        offset += 1
        if marker in (0xDA, 0xD9):
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            continue
        length = int.from_bytes(data[offset:offset + 2], 'big')
        if length < 2 or offset + length > len(data):
            raise ValueError('Truncated JPEG segment')
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            if length < 8:
                raise ValueError('Invalid JPEG frame header')
            height = int.from_bytes(data[offset + 3:offset + 5], 'big')
            width = int.from_bytes(data[offset + 5:offset + 7], 'big')
            return width, height
        offset += length
    raise ValueError('JPEG frame header not found')


class CameraPublisher(Node):
    def __init__(self):
        super().__init__('peter_remote_camera')
        self.declare_parameter('device', '/dev/video0')
        self.device = self.get_parameter('device').value
        self.capture = None
        self.configure_auto_controls()
        self.capture = self.open_camera()
        self.publisher = self.create_publisher(
            CompressedImage, '/peter/remote/video/compressed', qos_profile_sensor_data)
        self.failures = 0
        self.timer = self.create_timer(1.0 / TARGET_FPS, self.publish_frame)

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
        pipeline = (f'v4l2src device={self.device} ! '
                    f'image/jpeg,width=3840,height=2160,framerate={TARGET_FPS}/1 ! '
                    'appsink drop=true max-buffers=1 sync=false')
        candidates = [('GStreamer MJPEG passthrough', pipeline, cv2.CAP_GSTREAMER, None),
                      ('V4L2 MJPEG passthrough', self.device, cv2.CAP_V4L2, 'MJPG')]
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
                    cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 4)
                    if not cap.set(cv2.CAP_PROP_FORMAT, -1):
                        raise RuntimeError('backend does not support encoded JPEG capture')
                # Inspect JPEG headers without decoding image pixels.
                for _ in range(5):
                    self.read_jpeg(cap)
                fps = cap.get(cv2.CAP_PROP_FPS)
                if abs(fps - TARGET_FPS) > 0.5:
                    raise RuntimeError(f'negotiated {fps:.2f} FPS instead of {TARGET_FPS}')
                start = time.monotonic()
                for _ in range(TARGET_FPS):
                    self.read_jpeg(cap)
                measured = TARGET_FPS / (time.monotonic() - start)
                if measured < TARGET_FPS * 0.95:
                    raise RuntimeError(f'measured only {measured:.1f} FPS')
                self.get_logger().info(
                    f'Selected {label}: 3840x2160, negotiated {fps:.2f} FPS, '
                    f'probe {measured:.1f} FPS')
                return cap
            except (RuntimeError, ValueError, cv2.error) as exc:
                errors.append(f'{label}: {exc}')
                self.get_logger().warning(errors[-1])
                if cap is not None:
                    cap.release()
        raise RuntimeError('No backend passed 4K/20 validation:\n' + '\n'.join(errors))

    @staticmethod
    def read_jpeg(capture):
        ok, frame = capture.read()
        if not ok or frame is None:
            raise RuntimeError('Camera did not deliver a JPEG frame')
        data = frame.tobytes()
        if jpeg_resolution(data) != (3840, 2160):
            raise RuntimeError('Camera JPEG resolution is not 3840x2160')
        return data

    def publish_frame(self):
        try:
            data = self.read_jpeg(self.capture)
        except (RuntimeError, ValueError, cv2.error) as exc:
            self.failures += 1
            self.get_logger().error(str(exc))
            if self.failures >= 30:
                raise RuntimeError('Camera failed 30 consecutive reads; restart the node') from exc
            return
        self.failures = 0
        message = CompressedImage()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = 'peter_remote_camera_optical_frame'
        message.format = 'jpeg'
        # The ROS uint8[] setter accepts an array directly; passing bytes makes
        # it validate every JPEG byte in Python before constructing that array.
        message.data = array('B', data)
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
