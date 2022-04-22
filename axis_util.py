"""
Helper for working with AxisSpace's.
"""

# AxisInterval Fields

AXIS_START = 0
AXIS_END = 1


def axis_space_equal(space_1, space_2):
  """Return true if space_1 is equivalent to space 2."""
  if len(space_1) != len(space_2):
    return False

  for tag, intervals in space_1.items():
    if tag not in space_2:
      return False

    if not axis_intervals_equal(intervals, space_2[tag]):
      return False

  return True


def normalize_interval(interval):
  """Return normalized interval, points are always represented only as a start."""
  start = interval[AXIS_START]
  end = interval[AXIS_END] if AXIS_END in interval else None

  if end is None or start == end:
    return {AXIS_START: start}

  return {AXIS_START: start, AXIS_END: end}


def normalize_intervals(intervals):
  return [
      normalize_interval(interval)
      for interval in sorted(intervals,
                             key=lambda interval: interval[AXIS_START])
  ]


def axis_intervals_equal(intervals_1, intervals_2):
  return normalize_intervals(intervals_1) == normalize_intervals(intervals_2)
