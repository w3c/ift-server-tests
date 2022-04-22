"""Utility for geting info from fonts."""

import bisect
import io

from fontTools.ttLib import TTFont


def codepoints(font_data):
  """Returns the set of unicode codepoints in the CMAP of font_data."""
  font = TTFont(io.BytesIO(font_data))

  cmap = font["cmap"]
  all_codepoints = set()
  for table in cmap.tables:
    if not table.isUnicode():
      continue

    all_codepoints.update(table.cmap.keys())

  return all_codepoints


def axis_space(font_data):
  """Returns the axis space covered by the font, font_data."""
  font = TTFont(io.BytesIO(font_data))
  if "fvar" not in font:
    return {}

  fvar = font["fvar"]
  space = {}
  for axis in fvar.axes:
    tag = bytes(axis.axisTag, "utf8")
    if tag not in space:
      space[tag] = []

    if axis.minValue > axis.maxValue:
      raise Exception(
          f"Invalid font min value ({axis.minValue} > max value ({axis.maxValue} for "
          f"{tag} axis.")

    add_intervals(space[tag], {0: axis.minValue, 1: axis.maxValue})

  return space


def add_intervals(intervals, interval):
  """Union interval into intervals which is sorted by start value."""
  keys = [i[0] for i in intervals]
  index = bisect.bisect(keys, interval[0])
  intervals.insert(index, interval)

  merged = []
  i = 0
  while i < len(intervals):
    current = intervals[i]

    while i < len(intervals) - 1 and intersects(current, intervals[i + 1]):
      current = union(current, intervals[i + 1])
      i += 1

    merged.append(current)
    i += 1

  intervals[:] = merged


def union(interval_1, interval_2):
  """Returns the union of interval_1 and interval_2."""
  a_start = interval_1[0]
  b_start = interval_2[0]
  a_end = interval_1[1]
  b_end = interval_2[1]

  return {0: min(a_start, b_start), 1: max(a_end, b_end)}


def intersects(interval_1, interval_2):
  """Returns true if interval_1 and interval_2 intersect."""
  a_start = interval_1[0]
  b_start = interval_2[0]
  a_end = interval_1[1]
  b_end = interval_2[1]

  return b_start <= a_end and a_start <= b_end
