# Vehicle state feedback from the HAL. On the real vehicle this is decoded from
# the STM32 STATE_REPORT binary frame; in simulation the MCU bridge synthesizes
# it from the last command. Published on /vehicle/state (interface contract, ch4).
std_msgs/Header header

float32 steering_angle_rad    # measured front steering angle
float32 wheel_speed_mps       # measured longitudinal wheel speed
float32 brake                 # applied brake fraction, 0..1
float32 battery_voltage       # pack voltage in volts; 0.0 when unknown

uint16 fault_code             # 0 = OK; otherwise a bitfield of MCU fault flags
bool estop                    # true while emergency stop is latched
bool heartbeat_ok             # true while the host<->MCU heartbeat is within timeout
bool dry_run                  # true while real actuation is disabled
