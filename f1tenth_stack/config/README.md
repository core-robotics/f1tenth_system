# Vehicle-specific VESC configuration

VESC speed, steering, and device-path parameters are physical-vehicle
calibrations. They must not share an implicit default across cars.

- `vesc_car3.yaml`: vehicle 3 (`/dev/ttyMOTOR`)
- `vesc_car4.yaml`: vehicle 4 (`/dev/sensors/vesc`)

Every vehicle bringup requires an explicit `vesc_config` argument. For example:

```bash
ros2 launch f1tenth_stack bringup_launch.py \
  vesc_config:=/absolute/path/to/vesc_car3.yaml
```

For SLAM mapping, add `publish_odom_tf:=true`. Do not add `publish_tf` to a
vehicle YAML: the launch argument is the single owner of that mode switch.

Do not use `.gitignore`, `assume-unchanged`, or `skip-worktree` to manage a
tracked calibration. Add a new vehicle-specific file or pass an external
deployment config with `vesc_config:=...` instead.
