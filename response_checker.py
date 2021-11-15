"""
Helper for checking common cases on incremental font transfer server responses.
"""
import subprocess
import tempfile

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
    return self

  def format_is(self, patch_format):
    response = self.response()
    self.test_case.assertEqual(response[PATCH_FORMAT], patch_format)
    return self

  def check_apply_patch_to(self, base, min_codepoints):
    """Checks that this response can be applied to base and covers at least min_codepoints."""
    response = self.response()

    if REPLACEMENT in response:
      base = bytes([])
      patch = response[REPLACEMENT]
    else:
      patch = response[PATCH]

    subset = self.decode_patch(base, patch, response[PATCH_FORMAT])
    # TODO(garretrieger): add assert message
    self.test_case.assertTrue(len(subset) > 0)
    self.font_has_at_least_codepoints(subset, min_codepoints)

    # TODO(garretrieger): test checksums
    # TODO(garretrieger): font shapes identical to original for subset codepoints.

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

    return self

  def font_has_at_least_codepoints(self, font, subset):
    # TODO(garretrieger): implement.
    pass

  def decode_patch(self, base, patch, patch_format):
    """Attempts to apply patch to base. Returns decoded bytes."""
    if patch_format == VCDIFF:
      with tempfile.NamedTemporaryFile(
      ) as patch_file, tempfile.NamedTemporaryFile(
      ) as base_file, tempfile.NamedTemporaryFile() as subset_file:

        base_file.write(base)
        base_file.flush()
        patch_file.write(patch)
        patch_file.flush()

        result = subprocess.run([
            "xdelta3", "-f", "-d", "-s", base_file.name, patch_file.name,
            subset_file.name
        ],
                                check=True)
        self.test_case.assertEqual(result.returncode, 0)
        return subset_file.read()
    else:
      self.test_case.fail(f"Unsupported patch_format {patch_format}")
      return None
