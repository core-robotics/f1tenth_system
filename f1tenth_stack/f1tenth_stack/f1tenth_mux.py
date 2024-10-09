import rclpy
from rclpy.node import Node

from std_msgs.msg import Int8
from ackermann_msgs.msg import AckermannDriveStamped

class F1Tenth_mux(Node):
    def __init__(self):
        super().__init__('f1tenth_mux')
        self.joy_sub = self.create_subscription(AckermannDriveStamped, "teleop", self.joy_callback, 1)
        self.drive_sub = self.create_subscription(AckermannDriveStamped, "drive", self.drive_callback, 1)
        self.mode_sub = self.create_subscription(Int8, "dev/null", self.mode_callback, 1)
        
        self.joy_pub = self.create_publisher(AckermannDriveStamped, "input_mux/joy", 1)
        self.drive_pub = self.create_publisher(AckermannDriveStamped, "input_mux/drive", 1)
        
        self.pub = True
        
    def joy_callback(self, msg):
        if (self.pub):
            self.joy_pub.publish(msg)
    
    def drive_callback(self, msg):
        if (self.pub):
            self.drive_pub.publish(msg)
    
    def mode_callback(self, msg):
        self.pub = not self.pub

def main():
    rclpy.init()
    node = F1Tenth_mux()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass

    node.destroy_node()
    rclpy.shutdown()