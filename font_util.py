"""Utility for geting info from fonts."""

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
