"""Report received image dimensions and one-second receive FPS every ten seconds."""
import time

import cv2
import numpy as np
import rclpy
from rclpy.clock import Clock, ClockType
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage


class ImageSubscriber(Node):
    def __init__(self):
        super().__init__('peter_main_image_subscriber')
        self.resolution = None
        self.frames = 0
        self.invalid_frames = 0
        self.window_start = time.monotonic()
        self.last_report = self.window_start
        self.subscription = self.create_subscription(
            CompressedImage, '/peter/remote/video/compressed',
            self.receive_image, qos_profile_sensor_data)
        # Statistics use wall time even when ROS simulation time is enabled.
        self.timer = self.create_timer(
            1.0, self.report_statistics, clock=Clock(clock_type=ClockType.STEADY_TIME))

    def receive_image(self, message):
        try:
            image = cv2.imdecode(np.frombuffer(message.data, dtype=np.uint8),
                                 cv2.IMREAD_COLOR)
        except (cv2.error, ValueError):
            image = None
        if image is None:
            self.invalid_frames += 1
            return
        height, width = image.shape[:2]
        self.resolution = (width, height)
        self.frames += 1

    def report_statistics(self):
        now = time.monotonic()
        elapsed = now - self.window_start
        if elapsed <= 0:
            return
        fps = self.frames / elapsed
        invalid = self.invalid_frames
        self.frames = 0
        self.invalid_frames = 0
        self.window_start = now
        if now - self.last_report < 10.0:
            return
        self.last_report = now
        resolution = ('unknown' if self.resolution is None
                      else f'{self.resolution[0]}x{self.resolution[1]}')
        self.get_logger().info(
            f'Image resolution: {resolution}; FPS: {fps:.2f} '
            f'(last {elapsed:.2f}s, invalid images: {invalid})')


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = ImageSubscriber()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
