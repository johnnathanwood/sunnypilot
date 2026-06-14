"""
Copyright (c) 2021-, Haibin Wen, sunnypilot, and a number of other contributors.

This file is part of sunnypilot and is licensed under the MIT License.
See the LICENSE.md file in the root directory for more details.
"""
import numpy as np

import pyray as rl
from openpilot.common.constants import CV
from openpilot.selfdrive.ui.ui_state import ui_state
from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.lib.text_measure import measure_text_cached


class ChevronOptions:
  OFF = 0
  DISTANCE_ONLY = 1
  SPEED_ONLY = 2
  TTC_ONLY = 3
  ALL = 4


class ChevronMetrics:
  def __init__(self):
    self._lead_status_alpha: float = 0.0
    self._font = gui_app.font(FontWeight.SEMI_BOLD)

  def update_alpha(self, has_lead: bool):
    """Update the alpha value for fade in/out animation"""
    if not has_lead:
      self._lead_status_alpha = max(0.0, self._lead_status_alpha - 0.05)
    else:
      self._lead_status_alpha = min(1.0, self._lead_status_alpha + 0.1)

  def should_render(self) -> bool:
    """Check if dev UI should be rendered"""
    return ui_state.chevron_metrics != ChevronOptions.OFF and self._lead_status_alpha > 0.0

  def _draw_lead(self, lead_data, lead_vehicle, v_ego: float, rect: rl.Rectangle):
    """Draw lead vehicle status information (distance, speed, TTC)"""
    if not self.should_render():
      return

    d_rel = lead_data.dRel
    v_rel = lead_data.vRel

    if not lead_vehicle.chevron or len(lead_vehicle.chevron) < 2:
      return

    chevron_x = lead_vehicle.chevron[1][0]
    chevron_y = lead_vehicle.chevron[1][1]
    sz = np.clip((25 * 30) / (d_rel / 3 + 30), 15.0, 30.0) * 2.35

    text_lines = self._build_text_lines(d_rel, v_rel, v_ego)
    if not text_lines:
      return

    self._render_text_lines(text_lines, chevron_x, chevron_y, sz, rect)

  @staticmethod
  def _build_text_lines(d_rel: float, v_rel: float, v_ego: float) -> list[str]:
    """Build text lines based on chevron info setting"""
    text_lines = []

    # Distance
    if ui_state.chevron_metrics == ChevronOptions.DISTANCE_ONLY or ui_state.chevron_metrics == ChevronOptions.ALL:
      val = max(0.0, d_rel)
      unit = "m" if ui_state.is_metric else "ft"
      if not ui_state.is_metric:
        val *= 3.28084
      text_lines.append(f"{val:.0f} {unit}")

    # Speed
    if ui_state.chevron_metrics == ChevronOptions.SPEED_ONLY or ui_state.chevron_metrics == ChevronOptions.ALL:
      multiplier = CV.MS_TO_KPH if ui_state.is_metric else CV.MS_TO_MPH
      val = max(0.0, (v_rel + v_ego) * multiplier)
      unit = "km/h" if ui_state.is_metric else "mph"
      text_lines.append(f"{val:.0f} {unit}")

    # Time to collision
    if ui_state.chevron_metrics == ChevronOptions.TTC_ONLY or ui_state.chevron_metrics == ChevronOptions.ALL:
      val = (d_rel / v_ego) if (d_rel > 0 and v_ego > 0) else 0.0
      ttc_text = f"{val:.1f} s" if (0 < val < 200) else "---"
      text_lines.append(ttc_text)

    return text_lines

  def _render_text_lines(self, text_lines: list[str], chevron_x: float, chevron_y: float,
                         sz: float, rect: rl.Rectangle):
    """Render text lines with proper centering and positioning"""
    font_size = 40
    line_height = 50
    margin = 20

    text_y = chevron_y + sz + 15
    total_height = len(text_lines) * line_height

    # Adjust Y position if text would go off screen
    if text_y + total_height > rect.height - margin:
      y_max = min(chevron_y, rect.height - margin)
      text_y = y_max - 15 - total_height
      text_y = max(margin, text_y)

    alpha = int(255 * self._lead_status_alpha)
    text_color = rl.Color(255, 255, 255, alpha)
    shadow_color = rl.Color(0, 0, 0, int(200 * self._lead_status_alpha))

    for i, line in enumerate(text_lines):
      y = int(text_y + (i * line_height))
      if y + line_height > rect.height - margin:
        break

      # Measure actual text width for proper centering
      text_size = measure_text_cached(self._font, line, font_size, 0)
      text_width = text_size.x

      # Center the text horizontally on the chevron
      x = int(chevron_x - text_width / 2)
      x = int(np.clip(x, margin, rect.width - text_width - margin))

      # Draw shadow
      rl.draw_text_ex(self._font, line, rl.Vector2(x + 2, y + 2), font_size, 0, shadow_color)
      # Draw text
      rl.draw_text_ex(self._font, line, rl.Vector2(x, y), font_size, 0, text_color)

  def draw_lead_status(self, sm, radar_state, rect, lead_vehicles):
    lead_one = radar_state.leadOne
    lead_two = radar_state.leadTwo

    has_lead_one = lead_one.status if lead_one else False
    has_lead_two = lead_two.status if lead_two else False

    self.update_alpha(has_lead_one or has_lead_two)

    # Tracking border boxes ride the Developer UI ("debug") gate, independent of the
    # chevron-metrics text setting, so they show alongside the LONG: BRAKE/COAST/GAS chip.
    self._draw_lead_borders(radar_state, rect, lead_vehicles, has_lead_one, has_lead_two)

    if not self.should_render():
      return

    v_ego = sm['carState'].vEgo

    if has_lead_one and lead_vehicles[0].chevron:
      self._draw_lead(lead_one, lead_vehicles[0], v_ego, rect)

    if has_lead_two and lead_vehicles[1].chevron:
      d_rel_diff = abs(lead_one.dRel - lead_two.dRel) if has_lead_one else float('inf')
      if d_rel_diff > 3.0:
        self._draw_lead(lead_two, lead_vehicles[1], v_ego, rect)

  def _draw_lead_borders(self, radar_state, rect, lead_vehicles, has_lead_one: bool, has_lead_two: bool):
    """Draw outline boxes around the tracked lead(s).

    Gated on the Developer UI flag (DevUIInfo) so the boxes only show in debug mode,
    beside the LONG: BRAKE/COAST/GAS chip, and independent of the chevron-metrics text
    setting. Fades with the shared _lead_status_alpha maintained by update_alpha().
    """
    if not ui_state.developer_ui:  # OFF (0 / None) -> no boxes
      return
    if self._lead_status_alpha <= 0.0:
      return

    lead_one = radar_state.leadOne
    lead_two = radar_state.leadTwo

    if has_lead_one and lead_vehicles[0].chevron and len(lead_vehicles[0].chevron) >= 2:
      apex = lead_vehicles[0].chevron[1]
      self._draw_lead_box(apex[0], apex[1], lead_one.dRel, rect)

    if has_lead_two and lead_vehicles[1].chevron and len(lead_vehicles[1].chevron) >= 2:
      d_rel_diff = abs(lead_one.dRel - lead_two.dRel) if has_lead_one else float('inf')
      if d_rel_diff > 3.0:
        apex = lead_vehicles[1].chevron[1]
        self._draw_lead_box(apex[0], apex[1], lead_two.dRel, rect)

  def _draw_lead_box(self, center_x: float, center_y: float, d_rel: float, rect: rl.Rectangle):
    """Draw a single rounded outline box centered on a lead's chevron apex, with a
    distance-only label. Color by distance (red <5 m, amber <15 m, white), sized with
    the same distance formula as the chevron so it scales naturally."""
    sz = np.clip((25 * 30) / (d_rel / 3 + 30), 15.0, 30.0) * 2.35
    box_w = sz * 2.6
    box_h = sz * 2.2

    # Skip if the apex projects off-frame; otherwise clamp the box fully into the view.
    if not (rect.x <= center_x <= rect.x + rect.width and rect.y <= center_y <= rect.y + rect.height):
      return
    rx = float(np.clip(center_x - box_w / 2.0, rect.x, rect.x + rect.width - box_w))
    ry = float(np.clip(center_y - box_h * 0.35, rect.y, rect.y + rect.height - box_h))

    if d_rel < 5:
      r, g, b = 255, 0, 0
    elif d_rel < 15:
      r, g, b = 255, 188, 0
    else:
      r, g, b = 255, 255, 255
    alpha = self._lead_status_alpha
    color = rl.Color(r, g, b, int(255 * alpha))
    shadow = rl.Color(0, 0, 0, int(160 * alpha))

    rl.draw_rectangle_rounded_lines_ex(rl.Rectangle(rx + 2, ry + 2, box_w, box_h), 0.15, 8, 4, shadow)
    rl.draw_rectangle_rounded_lines_ex(rl.Rectangle(rx, ry, box_w, box_h), 0.15, 8, 4, color)

    # Distance-only label at the box top-left (object-detection style).
    val = max(0.0, d_rel)
    unit = "m" if ui_state.is_metric else "ft"
    if not ui_state.is_metric:
      val *= 3.28084
    label = f"{val:.0f} {unit}"
    font_size = 30
    lx = int(rx)
    ly = max(int(rect.y), int(ry - font_size - 4))
    rl.draw_text_ex(self._font, label, rl.Vector2(lx + 2, ly + 2), font_size, 0, rl.Color(0, 0, 0, int(200 * alpha)))
    rl.draw_text_ex(self._font, label, rl.Vector2(lx, ly), font_size, 0, color)
