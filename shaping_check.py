"""Utility for comparing shaping of fonts."""

import random
import uharfbuzz


# pylint: disable=too-many-locals
def identical_shaping(font_1_bytes: bytes, font_2_bytes: bytes,
                      codepoints: set[int]) -> bool:
  """Returns true if font_1 and font_2 shape identically for randomly generated test strings."""
  if not codepoints:
    return True

  font_1 = to_font(font_1_bytes)
  font_2 = to_font(font_2_bytes)

  for _ in range(len(codepoints) * 4):
    text = random_test_string(codepoints)
    [infos_1, positions_1] = shape(font_1, text)
    [infos_2, positions_2] = shape(font_2, text)

    for info_1, info_2, pos_1, pos_2 in zip(infos_1, infos_2, positions_1,
                                            positions_2):
      gid_1 = info_1.codepoint
      gid_2 = info_2.codepoint
      # TODO(garretrieger): check glyph outlines are equivalent instead of comparing ids which could
      #                     change.
      if gid_1 != gid_2:
        return False

      if pos_1.x_offset != pos_2.x_offset:
        return False

      if pos_1.y_offset != pos_2.y_offset:
        return False

  return True


# pylint: disable=no-member
def shape(font, text):
  """Shapes the given text with font and returns the glyph infos and positions data."""
  buf = uharfbuzz.Buffer()
  buf.add_str(text)
  buf.guess_segment_properties()
  uharfbuzz.shape(font, buf, {})

  return [buf.glyph_infos, buf.glyph_positions]


def random_test_string(codepoints: set[int]) -> str:
  """Generates a string that is a random ordering of codepoints."""
  codepoint_list = list(sorted(codepoints))
  random.shuffle(codepoint_list)

  result = ""
  for codepoint in codepoint_list:
    result += chr(codepoint)

  return result


# pylint: disable=no-member
def to_font(font_bytes: bytes):
  """Converts font_bytes into a uharfbuzz Font."""
  blob = uharfbuzz.Blob(font_bytes)
  face = uharfbuzz.Face(blob)
  return uharfbuzz.Font(face)
