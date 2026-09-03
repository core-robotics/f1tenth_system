# MIT License

"""Joystick teleoperation with a toggle button instead of a deadman button."""

import typing

import ackermann_msgs.msg
import rclpy
from rclpy.node import Node
from rclpy.parameter import PARAMETER_SEPARATOR_STRING
import sensor_msgs.msg
import std_msgs.msg


class JoyToggleTeleop(Node):
    """Publish Ackermann commands while manual mode is toggled on."""

    def __init__(self) -> None:
        super().__init__(
            'joy_teleop',
            allow_undeclared_parameters=True,
            automatically_declare_parameters_from_overrides=True,
        )

        config = self._retrieve_config().get('human_control', {})
        if not isinstance(config, dict):
            raise RuntimeError('human_control configuration must be a mapping')

        mappings = config.get('axis_mappings', {})
        try:
            speed = mappings['drive-speed']
            steering = mappings['drive-steering_angle']
            self.toggle_button = int(config.get('toggle_button', 4))
            self.speed_axis = int(speed['axis'])
            self.speed_scale = float(speed.get('scale', 1.0))
            self.speed_offset = float(speed.get('offset', 0.0))
            self.steering_axis = int(steering['axis'])
            self.steering_scale = float(steering.get('scale', 1.0))
            self.steering_offset = float(steering.get('offset', 0.0))
            topic_name = str(config.get('topic_name', 'teleop'))
            manual_lock_topic = str(config.get('manual_lock_topic', 'manual_control'))
            manual_lock_rate = float(config.get('manual_lock_publish_rate', 10.0))
        except (KeyError, TypeError, ValueError) as error:
            raise RuntimeError('invalid human_control configuration') from error

        if manual_lock_rate <= 0.0:
            raise RuntimeError('manual_lock_publish_rate must be greater than zero')

        self.manual_enabled = False
        self.toggle_button_pressed = False
        self.publisher = self.create_publisher(
            ackermann_msgs.msg.AckermannDriveStamped, topic_name, 1)
        self.manual_lock_publisher = self.create_publisher(
            std_msgs.msg.Bool, manual_lock_topic, 1)
        self.subscription = self.create_subscription(
            sensor_msgs.msg.Joy, 'joy', self._joy_callback, 1)
        self.manual_lock_timer = self.create_timer(
            1.0 / manual_lock_rate, self._publish_manual_lock)

        # The mux treats an expired lock as locked.  Publish the initial OFF
        # state immediately, then keep it alive with the heartbeat timer.
        self._publish_manual_lock()

        self.get_logger().info(
            f'Manual control is toggle-enabled on joystick button {self.toggle_button}'
        )

    def _joy_callback(self, msg: sensor_msgs.msg.Joy) -> None:
        button_pressed = (
            len(msg.buttons) > self.toggle_button
            and msg.buttons[self.toggle_button] == 1
        )

        # Toggle only on the 0 -> 1 transition, so holding LB does not toggle
        # repeatedly while joy_node is publishing autorepeat messages.
        rising_edge = button_pressed and not self.toggle_button_pressed
        self.toggle_button_pressed = button_pressed

        if rising_edge:
            self.manual_enabled = not self.manual_enabled
            self.get_logger().info(
                f'Manual control {"enabled" if self.manual_enabled else "disabled"}')
            self._publish_manual_lock()

        if rising_edge and not self.manual_enabled:
            self._publish_command(0.0, 0.0)
        elif self.manual_enabled:
            self._publish_command(
                self._mapped_axis(msg, self.speed_axis, self.speed_scale, self.speed_offset),
                self._mapped_axis(
                    msg, self.steering_axis, self.steering_scale, self.steering_offset),
            )

    def _mapped_axis(
        self,
        msg: sensor_msgs.msg.Joy,
        axis: int,
        scale: float,
        offset: float,
    ) -> float:
        if 0 <= axis < len(msg.axes):
            return msg.axes[axis] * scale + offset
        return 0.0

    def _publish_command(self, speed: float, steering_angle: float) -> None:
        msg = ackermann_msgs.msg.AckermannDriveStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.drive.speed = speed
        msg.drive.steering_angle = steering_angle
        self.publisher.publish(msg)

    def _publish_manual_lock(self) -> None:
        msg = std_msgs.msg.Bool()
        msg.data = self.manual_enabled
        self.manual_lock_publisher.publish(msg)

    def _retrieve_config(self) -> typing.Dict[str, typing.Any]:
        config: typing.Dict[str, typing.Any] = {}
        for parameter_name in sorted(self._parameters.keys()):
            self._insert_dict(
                config,
                parameter_name,
                self.get_parameter(parameter_name).value,
            )
        return config

    def _insert_dict(
        self,
        dictionary: typing.Dict[str, typing.Any],
        key: str,
        value: typing.Any,
    ) -> None:
        split = key.partition(PARAMETER_SEPARATOR_STRING)
        if split[0] == key and split[1] == '' and split[2] == '':
            dictionary[key] = value
            return

        if split[0] not in dictionary:
            dictionary[split[0]] = {}
        self._insert_dict(dictionary[split[0]], split[2], value)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = JoyToggleTeleop()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
