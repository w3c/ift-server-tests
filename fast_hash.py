"""
Implements the fast hash hashing algorithm as specified here:
https://w3c.github.io/IFT/Overview.html#computing-checksums
and https://github.com/ztanml/fast-hash
"""

# Constant values come from fast hash: https://github.com/ztanml/fast-hash
SEED = 0x11743e80f437ffe6
M = 0x880355f21e6d1965


def _uint64(value):
  return value % 18446744073709551616


def _mix(value):
  value = value ^ value >> 23
  value = _uint64(value * 0x2127599bf4325c37)
  value = value ^ (value >> 47)
  return value


def compute(data):
  """Computes the fast hash of data which is a byte array."""

  # When casting byte arrays into unsigned 64 bit integers the bytes are in little
  # endian order. That is the smallest index is the least significant byte.
  hash_value = SEED ^ _uint64(len(data) * M)
  for i in range(0, len(data) - 7, 8):
    next_value = int.from_bytes(data[i:i + 8], byteorder='little', signed=False)
    hash_value = _uint64((hash_value ^ _mix(next_value)) * M)

  remaining = len(data) % 8
  if not remaining:
    return _mix(hash_value)

  last_value = data[len(data) - remaining:] + bytes([0] * (8 - remaining))
  last_value = int.from_bytes(last_value, byteorder='little', signed=False)
  return _mix(_uint64((hash_value ^ _mix(last_value)) * M))
