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
    RANGE_DELTAS: bytes([0X41, 0X00]),
}

# Patch Formats
VCDIFF = 0
BROTLI = 1

# TODO(garretrieger): add variations of set encoding.


class ValidRequests:

  MINIMAL_REQUEST = dumps({
      PROTOCOL_VERSION: 0,
      ACCEPT_PATCH_FORMAT: [VCDIFF],
      CODEPOINTS_NEEDED: COMPRESSED_SET_41,
  })
