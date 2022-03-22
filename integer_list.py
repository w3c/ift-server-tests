"""Decoder for incxfer IntegerList's (https://w3c.github.io/IFT/Overview.html#integerlist)."""

from conformance_exception import ConformanceException


def decode(encoded_bytes: bytes) -> list[int]:
  """Decodes an integer list encoded by https://w3c.github.io/IFT/Overview.html#integerlist."""
  deltas = []
  decoder = Decoder(encoded_bytes)
  while decoder.has_more():
    deltas.append(decoder.next_int())

  values = []
  last_value = 0
  for delta in deltas:
    last_value = delta + last_value
    values.append(last_value)
  return values


def decode_zig_zag(value: int) -> int:
  if value & 1:
    return int(-((value + 1) / 2))
  return int(value / 2)


class Decoder:
  """Stores state for decoding an integer list."""

  def __init__(self, encoded_bytes: bytes):
    self.encoded_bytes = encoded_bytes
    self.index = 0

  def next_int(self) -> int:
    """Reads the next integer from encoded_bytes starting at index."""
    if not self.has_more():
      return 0

    value = 0
    bytes_read = 0
    while bytes_read < 5:
      next_byte = self.read_byte()
      bytes_read += 1

      if bytes_read == 1 and next_byte == 0x80:
        raise ConformanceException("Leading 0's are not allowed",
                                   "conform-uintbase128-illegal")
      if value & 0xFE000000:
        raise ConformanceException("UIntBase128 exceeds 2^32-1.",
                                   "conform-uintbase128-illegal")

      value = (value << 7) | (next_byte & 0x7F)

      if not 0x80 & next_byte:
        return decode_zig_zag(value)

    raise ConformanceException("UIntBase128 has more than 5 bytes.",
                               "conform-uintbase128-illegal")

  def has_more(self) -> bool:
    return self.index < len(self.encoded_bytes)

  def read_byte(self) -> int:
    if self.index < len(self.encoded_bytes):
      self.index += 1
      return self.encoded_bytes[self.index - 1]
    raise ConformanceException("Out of bounds read.",
                               "conform-uintbase128-illegal")
