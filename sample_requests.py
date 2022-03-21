"""
A collection of valid and invalid requests for use with an incremental font transfer
server.
"""

from cbor2 import dumps

# PatchRequest Fields
PROTOCOL_VERSION = 0
ACCEPT_PATCH_FORMAT = 1
CODEPOINTS_HAVE = 2
CODEPOINTS_NEEDED = 3
INDICES_HAVE = 4
INDICES_NEEDED = 5
AXIS_SPACE_HAVE = 6
AXIS_SPACE_NEEDED = 7
ORDERING_CHECKSUM = 8
ORIGINAL_FONT_CHECKSUM = 9
BASE_CHECKSUM = 10
CONNECTION_SPEED = 11

# CompressedSet Fields
SPARSE_BIT_SET = 0
RANGE_DELTAS = 1

COMPRESSED_SET_41 = {
    RANGE_DELTAS: bytes([0x41, 0x00]),
}

COMPRESSED_SET_42 = {
    RANGE_DELTAS: bytes([0x42, 0x00]),
}

# Patch Formats
VCDIFF = 0
BROTLI = 1

# TODO(garretrieger): add variations of set encoding.


class ValidRequests:
  """Helper that holds sample requests, and methods to produce them."""

  MINIMAL_REQUEST = dumps({
      PROTOCOL_VERSION: 0,
      ACCEPT_PATCH_FORMAT: [VCDIFF],
      CODEPOINTS_NEEDED: COMPRESSED_SET_41,
  })

  # pylint: disable=no-self-argument
  def compressed_set(codepoints):
    """Returns a compressed set containing the given codepoints."""
    # Simplistic implementation that encodes each point as a single range.
    last_cp = 0
    deltas = []
    for codepoint in sorted(codepoints):
      delta = codepoint - last_cp
      deltas.append(delta)
      deltas.append(0)
      last_cp = codepoint

    return {
        RANGE_DELTAS: bytes(deltas),
    }

  # pylint: disable=no-self-argument
  def minimal_patch_request(base_codepoints,
                            new_codepoints,
                            original_checksum,
                            base_checksum,
                            ordering_checksum=None):
    """Returns a basic patch request with the given parameters."""
    have_set = ValidRequests.compressed_set(base_codepoints)
    needed_set = ValidRequests.compressed_set(new_codepoints)
    obj = {
        PROTOCOL_VERSION: 0,
        ACCEPT_PATCH_FORMAT: [VCDIFF],
        ORIGINAL_FONT_CHECKSUM: original_checksum,
        BASE_CHECKSUM: base_checksum,
    }
    if ordering_checksum is not None:
      obj[ORDERING_CHECKSUM] = ordering_checksum
      obj[INDICES_HAVE] = have_set
      obj[INDICES_NEEDED] = needed_set
    else:
      obj[CODEPOINTS_HAVE] = have_set
      obj[CODEPOINTS_NEEDED] = needed_set


    return dumps(obj)
