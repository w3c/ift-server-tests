"""
Helper for checking common cases on incremental font transfer server responses.
"""

from cbor2 import loads

# PatchResponse Fields

PROTOCOL_VERSION = 0
PATCH_FORMAT = 1
PATCH = 2
REPLACEMENT = 3
ORIGINAL_FONT_CHECKSUM = 4
PATCHED_CHECKSUM = 5
CODEPOINT_ORDERING = 6
ORDERING_CHECKSUM = 7
SUBSET_AXIS_SPACE = 8
ORIGINAL_AXIS_SPACE = 9

# Patch Formats

VCDIFF = 0
BROTLI = 1

PATCH_FORMATS = {VCDIFF, BROTLI}

class ResponseChecker:
  """Defines a set of common checks against a IFT server response."""

  def __init__(self, test_case, response):
    self.test_case = test_case
    self.status_code = response.status
    self.response_data = response.read()
    self.response_obj = None
    self.url = response.url

  def successful_response_checks(self):
    """Checks all of the invariants that should be true on a successful response."""
    self.test_case.assertEqual(
        self.status_code, 200,
        f"Status code must be success (200) for {self.url} (2.5)")
    self.test_case.assertEqual(
        self.response_data[:4], bytes([0x49, 0x46, 0x54, 0x20]),
        f"Missing magic number 'IFT ' for {self.url} (2.5)")

    self.response_well_formed()

  def response(self):
    """Returns the decoded cbor response object."""
    if self.response_obj is None:
      self.response_obj = loads(self.response_data[4:])
      self.test_case.assertTrue(isinstance(self.response_obj, dict),
                                "response should be a dict. (2.3.4)")

    return self.response_obj

  def integer_list_well_formed(self, int_list):
    # TODO(garretrieger): check for requirements in 2.2.5
    pass

  def response_well_formed(self):
    """Checks the CBOR response object is well formed according to the spec."""
    response = self.response()
    self.test_case.assertTrue(PROTOCOL_VERSION in response,
                              "protocol_version must be set (2.3.4)")
    self.test_case.assertEqual(response[PROTOCOL_VERSION], 0,
                               "protocol_version must be set to 0 (2.3.4)")
    self.test_case.assertTrue(
        response[PATCH_FORMAT] in PATCH_FORMATS,
        f"patch_format {response[PATCH_FORMAT]} not in {PATCH_FORMATS}. (2.3.4)"
    )

    self.test_case.assertTrue(
        bool(PATCH in response) != bool(REPLACEMENT in response),
        "Only one of patch or replacement can be set. (2.3.4)")
    if PATCH in response or REPLACEMENT in response:
      self.test_case.assertTrue(isinstance(response[PATCHED_CHECKSUM], int),
                                "patched_checksum must be set. (2.3.4)")
      self.test_case.assertTrue(
          isinstance(response[ORIGINAL_FONT_CHECKSUM], int),
          "original_font_checksum must be set. (2.3.4)")

    if CODEPOINT_ORDERING in response:
      self.integer_list_well_formed(response[CODEPOINT_ORDERING])
      self.test_case.assertTrue(isinstance(response[ORDERING_CHECKSUM], int),
                                "ordering_checksum must be set. (2.3.4)")
