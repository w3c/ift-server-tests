from conformance_exception import ConformanceException

def decode(encoded_bytes: bytes) -> list[int]:
  """Decodes an integer list following encoded by https://w3c.github.io/IFT/Overview.html#integerlist."""
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


class Decoder:
  def __init__(self, encoded_bytes: bytes):
    self.encoded_bytes = encoded_bytes
    self.index = 0

  def decode_zig_zag(self, value: int) -> int:
    if value & 1:
      return int(-((value + 1) / 2))
    else:
      return int(value / 2)

  def next_int(self) -> int:
    """Reads the next integer from encoded_bytes starting at index."""
    if not self.has_more():
      return 0

    should_continue = True
    value = 0
    bytes_read = 0
    while bytes_read < 5:
      next_byte = self.read_byte()
      bytes_read += 1

      if bytes_read == 1 and next_byte == 0x80:
        raise ConformanceException("Leading 0's are not allowed", "conform-uintbase128-illegal")
      if value & 0xFE000000:
        raise ConformanceException("UIntBase128 exceeds 2^32-1.", "conform-uintbase128-illegal")

      value = (value << 7) | (next_byte & 0x7F);

      if not (0x80 & next_byte):
        return self.decode_zig_zag(value)

    raise ConformanceException("UIntBase128 has more than 5 bytes.", "conform-uintbase128-illegal")

  def has_more(self) -> bool:
    return self.index < len(self.encoded_bytes)

  def read_byte(self) -> int:
    if (self.index < len(self.encoded_bytes)):
      self.index += 1
      return self.encoded_bytes[self.index - 1]
    raise Error("out of bounds read.")
