"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""

from dataclasses import dataclass, field

from opendbc.car.hyundai.values import CAR


@dataclass
class CarTuningConfig:
  v_ego_stopping: float = 0.25
  v_ego_starting: float = 0.10
  stopping_decel_rate: float = 0.40
  lookahead_jerk_bp: list[float] = field(default_factory=lambda: [2., 5., 20.])
  lookahead_jerk_upper_v: list[float] = field(default_factory=lambda: [0.3, 0.45, 0.6])
  lookahead_jerk_lower_v: list[float] = field(default_factory=lambda: [0.3, 0.45, 0.6])
  longitudinal_actuator_delay: float = 0.50
  jerk_limits: float = 4.0
  # ISO 15622 speed-based UPPER jerk ceiling (m/s^3). Caps how fast accel can ramp up;
  # raising the low-speed point makes launch onset snappier. Default matches upstream.
  upper_jerk_speed_bp: list[float] = field(default_factory=lambda: [0.0, 5.0, 20.0])
  upper_jerk_speed_v: list[float] = field(default_factory=lambda: [2.0, 3.0, 2.0])
  # Standstill hold: minimum holding decel (m/s^2) commanded on a grade so the car
  # doesn't roll. 0.0 keeps upstream behavior (command 0 at stop, rely on the car's hold).
  stop_hold_margin: float = 0.0


# Default configurations for different car types
TUNING_CONFIGS = {
  "CANFD": CarTuningConfig(
    v_ego_stopping=0.30,
  ),
  "EV": CarTuningConfig(
    stopping_decel_rate=0.45,
    v_ego_stopping=0.35,
  ),
  "HYBRID": CarTuningConfig(
    v_ego_starting=0.15,
    stopping_decel_rate=0.45,
    v_ego_stopping=0.4,
  ),
  "DEFAULT": CarTuningConfig(
    v_ego_stopping=0.3,
  )
}

# Car-specific configs
CAR_SPECIFIC_CONFIGS = {
  CAR.KIA_NIRO_EV: CarTuningConfig(
    v_ego_stopping=0.1,
    stopping_decel_rate=0.3,
    jerk_limits=3.3,
  ),
  CAR.KIA_NIRO_PHEV_2022: CarTuningConfig(
    stopping_decel_rate=0.8,
    jerk_limits=5.0,
  ),
  # Kona 2022 (gas, CAN/radar SCC). Previously fell back to the generic DEFAULT tune,
  # which felt lazy off the line. Shorten only the *upper* lookahead window so it ramps
  # up to the planner's commanded accel sooner (more upper jerk). Braking jerk
  # (lookahead_jerk_lower_v) and the ISO 15622 ceilings are intentionally left at default.
  # Iteration 1 - validate with the tools/longitudinal_maneuvers report + on-road before tuning further.
  CAR.HYUNDAI_KONA_2022: CarTuningConfig(
    v_ego_stopping=0.3,                          # match prior DEFAULT behavior
    lookahead_jerk_upper_v=[0.25, 0.35, 0.45],   # default [0.3, 0.45, 0.6] -> snappier accel onset (mid-range)
    upper_jerk_speed_v=[2.5, 3.0, 2.0],          # default [2.0, 3.0, 2.0] -> mild low-speed bump (gas-step is delivery-bound, so don't over-raise)
    stop_hold_margin=0.3,                        # default 0.0 -> command a grade-sized holding decel at standstill (no rollback)
  ),
}
