"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import math
import time

import pyray as rl
from dataclasses import dataclass

from openpilot.common.constants import CV
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.text_measure import measure_text_cached


@dataclass
class UiElement:
  value: str
  label: str
  unit: str
  color: rl.Color
  val_text: str = ""
  label_text: str = ""
  unit_text: str = ""
  val_width: float = 0.0
  label_width: float = 0.0
  unit_width: float = 0.0
  total_width: float = 0.0

  def measure(self, font, font_size: int):
    self.label_text = f"{self.label} "
    self.val_text = self.value
    self.unit_text = f" {self.unit}" if self.unit else ""

    self.label_width = measure_text_cached(font, self.label_text, font_size, 0).x
    self.val_width = measure_text_cached(font, self.val_text, font_size, 0).x
    self.unit_width = measure_text_cached(font, self.unit_text, font_size, 0).x if self.unit else 0

    self.total_width = self.label_width + self.val_width + self.unit_width


class LeadInfoElement:
  @staticmethod
  def get_lead_status(sm):
    lead_one = sm['radarState'].leadOne
    return lead_one.present, lead_one.dRel, lead_one.vRel

  @staticmethod
  def get_lead_color(lead_d_rel: float, lead_v_rel: float = 0.0, use_v_rel: bool = False) -> rl.Color:
    if use_v_rel:
      if lead_v_rel < -4.4704:
        return rl.RED
      elif lead_v_rel < 0:
        return rl.Color(255, 188, 0, 255)  # Orange
    else:
      if lead_d_rel < 5:
        return rl.RED
      elif lead_d_rel < 15:
        return rl.Color(255, 188, 0, 255)  # Orange
    return rl.WHITE


class LateralControlElement:
  @staticmethod
  def get_lat_color(lat_active: bool, steer_override: bool, angle_steers: float = 0.0,
                    check_angle: bool = False) -> rl.Color:
    color = rl.WHITE
    if lat_active:
      color = rl.Color(145, 155, 149, 255) if steer_override else rl.Color(0, 255, 0, 255)

    if check_angle and lat_active:
      if abs(angle_steers) > 180:
        color = rl.RED
      elif abs(angle_steers) > 90:
        color = rl.Color(255, 188, 0, 255)
      else:
        # Keep green/grey from above
        pass
    elif check_angle and not lat_active:
      if abs(angle_steers) > 180:
        color = rl.RED
      elif abs(angle_steers) > 90:
        color = rl.Color(255, 188, 0, 255)

    return color


class RelDistElement(LeadInfoElement):
  def __init__(self):
    self.unit = "m"

  def update(self, sm, is_metric: bool) -> UiElement:
    lead_status, lead_d_rel, _ = self.get_lead_status(sm)
    value = f"{lead_d_rel:.0f}" if lead_status else "-"
    color = self.get_lead_color(lead_d_rel) if lead_status else rl.WHITE
    return UiElement(value, "REL DIST", self.unit, color)


class RelSpeedElement(LeadInfoElement):
  def __init__(self):
    self.unit = "km/h"

  def update(self, sm, is_metric: bool) -> UiElement:
    lead_status, _, lead_v_rel = self.get_lead_status(sm)

    self.unit = "km/h" if is_metric else "mph"

    conversion = CV.MS_TO_KPH if is_metric else CV.MS_TO_MPH
    value = f"{lead_v_rel * conversion:.0f}" if lead_status else "-"
    color = self.get_lead_color(0, lead_v_rel, use_v_rel=True) if lead_status else rl.WHITE

    return UiElement(value, "REL SPEED", self.unit, color)


class SteeringAngleElement(LateralControlElement):
  def __init__(self):
    self.unit = ""

  def update(self, sm, is_metric: bool) -> UiElement:
    car_state = sm['carState']
    angle_steers = car_state.steeringAngleDeg
    lat_active = sm['carControl'].latActive
    steer_override = car_state.steeringPressed

    value = f"{angle_steers:.1f}°"
    color = self.get_lat_color(lat_active, steer_override, angle_steers, check_angle=True)

    return UiElement(value, "REAL STEER", self.unit, color)


class DesiredSteeringAngleElement(LateralControlElement):
  def __init__(self):
    self.unit = ""

  def update(self, sm, is_metric: bool) -> UiElement:
    car_state = sm['carState']
    controls_state = sm['controlsState']
    lat_active = sm['carControl'].latActive
    angle_steers = car_state.steeringAngleDeg
    steer_angle_desired = controls_state.lateralControlState.angleState.steeringAngleDeg

    value = f"{steer_angle_desired:.1f}°" if lat_active else "-"

    color = rl.WHITE
    if lat_active:
      if abs(angle_steers) > 180:
        color = rl.RED
      elif abs(angle_steers) > 90:
        color = rl.Color(255, 188, 0, 255)
      else:
        color = rl.Color(0, 255, 0, 255)

    return UiElement(value, "DESIRED STEER", self.unit, color)


class ActualLateralAccelElement(LateralControlElement):
  def __init__(self):
    self.unit = "m/s^2"

  def update(self, sm, is_metric: bool) -> UiElement:
    controls_state = sm['controlsState']
    curvature = controls_state.curvature
    v_ego = sm['carState'].vEgo
    roll = sm['liveParameters'].roll if sm.valid['liveParameters'] else 0.0
    lat_active = sm['carControl'].latActive
    steer_override = sm['carState'].steeringPressed

    actual_lat_accel = (curvature * v_ego ** 2) - (roll * 9.81)
    value = f"{actual_lat_accel:.2f}"
    color = self.get_lat_color(lat_active, steer_override)

    return UiElement(value, "ACTUAL L.A.", self.unit, color)


class DesiredLateralAccelElement(LateralControlElement):
  def __init__(self):
    self.unit = "m/s^2"

  def update(self, sm, is_metric: bool) -> UiElement:
    controls_state = sm['controlsState']
    desired_curvature = controls_state.desiredCurvature
    v_ego = sm['carState'].vEgo
    roll = sm['liveParameters'].roll if sm.valid['liveParameters'] else 0.0
    lat_active = sm['carControl'].latActive
    steer_override = sm['carState'].steeringPressed

    desired_lat_accel = (desired_curvature * v_ego ** 2) - (roll * 9.81)
    value = f"{desired_lat_accel:.2f}" if lat_active else "-"
    color = self.get_lat_color(lat_active, steer_override)

    return UiElement(value, "DESIRED L.A.", self.unit, color)


class DesiredSteeringPIDElement(LateralControlElement):
  def __init__(self):
    self.unit = ""

  def update(self, sm, is_metric: bool) -> UiElement:
    car_state = sm['carState']
    controls_state = sm['controlsState']
    lat_active = sm['carControl'].latActive
    angle_steers = car_state.steeringAngleDeg
    steer_angle_desired = controls_state.lateralControlState.pidState.steeringAngleDesiredDeg

    value = f"{steer_angle_desired:.1f}°" if lat_active else "-"

    color = rl.WHITE
    if lat_active:
      if abs(angle_steers) > 180:
        color = rl.RED
      elif abs(angle_steers) > 90:
        color = rl.Color(255, 188, 0, 255)
      else:
        color = rl.Color(0, 255, 0, 255)

    return UiElement(value, "DESIRED STEER", self.unit, color)


class AEgoElement:
  def __init__(self):
    self.unit = "m/s^2"

  def update(self, sm, is_metric: bool) -> UiElement:
    a_ego = sm['carState'].aEgo
    value = f"{a_ego:.1f}"
    return UiElement(value, "ACC.", self.unit, rl.WHITE)


class LeadSpeedElement(LeadInfoElement):
  def __init__(self):
    self.unit = "km/h"

  def update(self, sm, is_metric: bool) -> UiElement:
    lead_status, _, lead_v_rel = self.get_lead_status(sm)
    v_ego = sm['carState'].vEgo

    self.unit = "km/h" if is_metric else "mph"

    conversion = CV.MS_TO_KPH if is_metric else CV.MS_TO_MPH
    value = f"{(lead_v_rel + v_ego) * conversion:.0f}" if lead_status else "-"
    color = self.get_lead_color(0, lead_v_rel, use_v_rel=True) if lead_status else rl.WHITE

    return UiElement(value, "L.S.", self.unit, color)


class FrictionCoefficientElement:
  def __init__(self):
    self.unit = ""

  def update(self, sm, is_metric: bool) -> UiElement:
    if ui_state.enforce_torque_control and ui_state.custom_torque_params and ui_state.torque_override_enabled:
      return UiElement(f"{ui_state.torque_override_friction:.3f}", "FRIC.", self.unit, rl.WHITE)

    ltp = sm['liveTorqueParameters']
    value = f"{ltp.frictionCoefficientFiltered:.3f}"
    color = rl.Color(0, 255, 0, 255) if ltp.liveValid else rl.WHITE
    return UiElement(value, "FRIC.", self.unit, color)


class LatAccelFactorElement:
  def __init__(self):
    self.unit = ""

  def update(self, sm, is_metric: bool) -> UiElement:
    if ui_state.enforce_torque_control and ui_state.custom_torque_params and ui_state.torque_override_enabled:
      return UiElement(f"{ui_state.torque_override_lat_accel_factor:.3f}", "L.A.F.", self.unit, rl.WHITE)

    ltp = sm['liveTorqueParameters']
    value = f"{ltp.latAccelFactorFiltered:.3f}"
    color = rl.Color(0, 255, 0, 255) if ltp.liveValid else rl.WHITE
    return UiElement(value, "L.A.F.", self.unit, color)


class SteeringTorqueEpsElement:
  def __init__(self):
    self.unit = "N·dm"

  def update(self, sm, is_metric: bool) -> UiElement:
    steering_torque_eps = sm['carState'].steeringTorqueEps
    value = f"{abs(steering_torque_eps):.1f}"
    return UiElement(value, "E.T.", self.unit, rl.WHITE)


class GpsInfoElement:
  @staticmethod
  def get_gps_data(sm):
    if sm.valid['gpsLocationExternal']:
      return sm['gpsLocationExternal'], True
    elif sm.valid['gpsLocation']:
      return sm['gpsLocation'], True
    return None, False


class BearingDegElement(GpsInfoElement):
  def __init__(self):
    self.unit = ""

  def update(self, sm, is_metric: bool) -> UiElement:
    gps_data, valid = self.get_gps_data(sm)
    if not valid:
      return UiElement("OFF | -", "B.D.", self.unit, rl.WHITE)

    bearing_accuracy_deg = gps_data.bearingAccuracyDeg
    bearing_deg = gps_data.bearingDeg

    if bearing_accuracy_deg != 180.0:
      value = f"{bearing_deg:.0f}°"
      if (337.5 <= bearing_deg <= 360) or (0 <= bearing_deg <= 22.5):
        dir_value = "N"
      elif 22.5 < bearing_deg < 67.5:
        dir_value = "NE"
      elif 67.5 <= bearing_deg <= 112.5:
        dir_value = "E"
      elif 112.5 < bearing_deg < 157.5:
        dir_value = "SE"
      elif 157.5 <= bearing_deg <= 202.5:
        dir_value = "S"
      elif 202.5 < bearing_deg < 247.5:
        dir_value = "SW"
      elif 247.5 <= bearing_deg <= 292.5:
        dir_value = "W"
      else:  # 292.5 < bearing_deg < 337.5
        dir_value = "NW"
    else:
      value = "-"
      dir_value = "OFF"

    return UiElement(f"{dir_value} | {value}", "B.D.", self.unit, rl.WHITE)


class AltitudeElement(GpsInfoElement):
  def __init__(self):
    self.unit = "m"

  def update(self, sm, is_metric: bool) -> UiElement:
    gps_data, valid = self.get_gps_data(sm)

    gps_accuracy = 0.0
    altitude = 0.0

    if valid:
      altitude = gps_data.altitude
      if sm.valid['gpsLocationExternal']:
        gps_accuracy = gps_data.horizontalAccuracy
      else:
        gps_accuracy = 1.0  # Simulate valid for legacy check

    value = f"{altitude:.1f}" if gps_accuracy != 0.0 else "-"
    return UiElement(value, "ALT.", self.unit, rl.WHITE)


class LongActionElement:
  # LONG indicator (manual-aware). Shows GAS / COAST / BRAKE / SLOW = what the car is doing
  # longitudinally, in BOTH modes:
  #   - openpilot in long control: classify its COMMANDED accel vs the natural coast accel
  #     (mirror get_coast_accel) -> above = GAS (green; incl. holding speed), below-with-lamp =
  #     BRAKE (red), below-without-lamp = SLOW (blue), riding it = COAST (gray).
  #   - driver in control (not longActive): classify the DRIVER's pedals -> gasPressed = GAS (amber),
  #     nothing = COAST (gray); the physical brake lamp reads BRAKE above.
  # Colour convention: green/red/blue = the comma is acting, amber = YOU are acting, gray = coasting.
  GAS_MARGIN = 0.03     # m/s^2 above coast to read GAS (small, so holding-against-drag counts as gas)
  BRAKE_MARGIN = 0.20   # m/s^2 below coast to read BRAKE
  STOPPED_V = 0.25      # m/s; commanding gas but stopped == SCC standstill hold (won't auto-resume)

  def __init__(self):
    self.unit = ""
    self._lamp_on_since = None   # monotonic ts the physical brake lamp came on

  @staticmethod
  def _coast_accel(v_ego: float, pitch: float) -> float:
    # mirror selfdrive/controls/lib/longitudinal_planner.get_coast_accel (grade + speed-dependent drag)
    return math.sin(pitch) * -9.81 + (-0.05 - 0.011 * v_ego - 0.00014 * v_ego ** 2)

  def update(self, sm, is_metric: bool) -> UiElement:
    cc = sm['carControl']
    cs = sm['carState']
    # brake lamp wins first, in EITHER mode: the car is physically braking (reverse-engineered msg
    # 1193 bit62). red = the comma's braking lit it; amber = the driver is braking.
    if cs.brakeLightsDEPRECATED:
      if self._lamp_on_since is None:
        self._lamp_on_since = time.monotonic()
      _d = time.monotonic() - self._lamp_on_since
      _lbl = ("BRAKE %ds" % _d) if _d >= 1.0 else "BRAKE"
      if cc.longActive and not cs.brakePressed:
        return UiElement(_lbl, "LONG", self.unit, rl.RED)
      return UiElement(_lbl, "LONG", self.unit, rl.Color(255, 188, 0, 255))
    self._lamp_on_since = None   # lamp OFF -> reset the on-duration timer

    if not cc.longActive:
      # MANUAL longitudinal: the driver owns the pedals (brake handled by the lamp above).
      if cs.gasPressed:
        return UiElement("GAS", "LONG", self.unit, rl.Color(255, 188, 0, 255))
      return UiElement("COAST", "LONG", self.unit, rl.Color(166, 166, 166, 255))

    accel = float(cc.actuators.accel)
    v = float(cs.vEgo)
    try:
      pitch = float(cc.orientationNED[1])
    except Exception:
      pitch = 0.0
    coast = self._coast_accel(v, pitch)

    # commanding below coast while the lamp is OFF = easing/decelerating without lighting the
    # brake lights -> SLOW (blue), not red BRAKE.
    if accel <= coast - self.BRAKE_MARGIN:
      return UiElement("SLOW", "LONG", self.unit, rl.Color(110, 160, 210, 255))
    # above the coast curve = adding power -> GAS (incl. holding speed against drag)
    if accel >= coast + self.GAS_MARGIN:
      if v < self.STOPPED_V:
        return UiElement("GAS held", "LONG", self.unit, rl.Color(255, 188, 0, 255))
      return UiElement("GAS", "LONG", self.unit, rl.Color(0, 255, 0, 255))
    # riding the coast curve: off the gas, not braking
    return UiElement("COAST", "LONG", self.unit, rl.Color(166, 166, 166, 255))
