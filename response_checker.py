"""
Helper for checking common cases on incremental font transfer server responses.
"""

import subprocess
import tempfile

from cbor2 import loads
import font_util
import fast_hash
from sample_requests import ValidRequests

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


def spec_link(tag):
  return f"https://w3c.github.io/IFT/Overview.html#{tag}"


class ResponseChecker:
  """Defines a set of common checks against a IFT server response."""

  def __init__(self, test_case, response, original_font_bytes):
    """Constructor."""
    self.test_case = test_case
    self.status_code = response.status
    self.response_data = response.read()
    self.response_obj = None
    self.url = response.url
    self.tested_ids = set()
    self.original_font_bytes = original_font_bytes
    self.base = bytes([])

  def print_tested_ids(self):
    for tag in self.tested_ids:
      print(f"tested conformance id: {tag}")

  def conform_message(self, tag, message):
    self.tested_ids.add(tag)
    return (f"Failed requirement {spec_link(tag)}\n"
            f"  {message}\n"
            f"  Request URL: {self.url}")

  def successful_response_checks(self):
    """Checks all of the invariants that should be true on a successful response."""
    self.test_case.assertEqual(
        self.status_code, 200,
        self.conform_message("conform-successful-response",
                             "Status code must be success (200)"))

    self.test_case.assertEqual(
        self.response_data[:4], bytes([0x49, 0x46, 0x54, 0x20]),
        self.conform_message("conform-magic-number",
                             "Missing magic number 'IFT '"))

    self.response_well_formed()
    return self

  def format_in(self, patch_formats):
    """Checks that format is one of the provided formats."""
    response = self.response()
    self.test_case.assertTrue(
        response[PATCH_FORMAT] in patch_formats,
        self.conform_message(
            "conform-response-patch-format",
            f"Patch format ({response[PATCH_FORMAT]}) must be "
            f"one of {patch_formats}"))
    return self

  def check_apply_patch_to(self, min_codepoints):
    """Checks that this response can be applied to base and covers at least min_codepoints."""
    response = self.response()

    base = self.base
    if REPLACEMENT in response:
      base = bytes([])
      patch = response[REPLACEMENT]
    else:
      patch = response[PATCH]

    subset = self.decode_patch(base, patch, response[PATCH_FORMAT])
    self.font_has_at_least_codepoints(subset, min_codepoints)
    self.patched_checksum_matches(subset)

    # TODO(garretrieger): font shapes identical to original for subset codepoints.
    return subset

  def extend(self, requester, new_codepoints, codepoint_map=None):
    """Make a second request that extends the font fetched by this one."""
    base = self.check_apply_patch_to(set())
    base_checksum = fast_hash.compute(base)
    original_checksum = self.original_font_checksum()
    base_codepoints = self.codepoints_in_response()
    ordering_checksum = self.ordering_checksum() if codepoint_map is not None else None

    if codepoint_map:
      base_codepoints = {codepoint_map[cp] for cp in base_codepoints}
      new_codepoints = {codepoint_map[cp] for cp in new_codepoints}

    request_cbor = ValidRequests.minimal_patch_request(
        base_codepoints, new_codepoints,
        original_checksum, base_checksum, ordering_checksum)

    response = requester(request_cbor)
    response.base = base
    return response

  def codepoints_in_response(self):
    base = self.check_apply_patch_to(set())
    return font_util.codepoints(base)

  def original_font_checksum(self):
    response = self.response()
    return response[ORIGINAL_FONT_CHECKSUM]

  def ordering_checksum(self):
    response = self.response()
    return response[ORDERING_CHECKSUM]

  def assert_has_codepoint_mapping(self):
    self.test_case.assertTrue(CODEPOINT_ORDERING in self.response(),
                              self.conform_message("conform-response-codepoint-ordering",
                                                   "codepoint_ordering must be set."))
    return self

  def codepoint_mapping(self):
    self.assert_has_codepoint_mapping()
    # TODO(garretrieger): decode the int list.
    return {}

  def response(self):
    """Returns the decoded cbor response object."""
    if self.response_obj is None:
      self.response_obj = loads(self.response_data[4:])
      self.test_case.assertTrue(
          isinstance(self.response_obj, dict),
          self.conform_message("conform-object",
                               "response must be a CBOR map."))

    return self.response_obj

  def integer_list_well_formed(self, int_list):
    # TODO(garretrieger): check for requirements in 2.2.5
    pass

  def response_well_formed(self):
    """Checks the CBOR response object is well formed according to the spec."""
    response = self.response()
    self.test_case.assertTrue(
        PROTOCOL_VERSION in response,
        self.conform_message("conform-response-protocol-version",
                             "protocol_version must be set."))

    self.test_case.assertEqual(
        response[PROTOCOL_VERSION], 0,
        self.conform_message("conform-response-protocol-version",
                             "protocol_version must be set to 0."))

    self.test_case.assertTrue(
        PATCH_FORMAT in response,
        self.conform_message("conform-response-valid-format",
                             "patch_format must be set."))
    self.test_case.assertTrue(
        response[PATCH_FORMAT] in PATCH_FORMATS,
        self.conform_message(
            "conform-response-valid-format",
            f"patch_format {response[PATCH_FORMAT]} not in {PATCH_FORMATS}."))

    self.test_case.assertTrue(
        bool(PATCH in response) != bool(REPLACEMENT in response),
        self.conform_message("conform-response-patch-or-replacement",
                             "Only one of patch or replacement can be set."))

    if PATCH in response or REPLACEMENT in response:
      self.test_case.assertTrue(
          isinstance(response[PATCHED_CHECKSUM], int),
          self.conform_message("conform-response-font-checksums",
                               "patched_checksum must be set."))
      self.test_case.assertTrue(
          isinstance(response[ORIGINAL_FONT_CHECKSUM], int),
          self.conform_message("conform-response-font-checksums",
                               "original_font_checksum must be set."))

      self.original_checksum_matches(self.original_font_bytes)

    if CODEPOINT_ORDERING in response:
      self.integer_list_well_formed(response[CODEPOINT_ORDERING])
      # TODO(garretrieger): is their a requirement to check the ordering checksum?
      self.test_case.assertTrue(
          isinstance(response[ORDERING_CHECKSUM], int),
          self.conform_message("conform-response-ordering-checksum",
                               "ordering_checksum must be set."))

    return self

  def patched_checksum_matches(self, font_data):
    response = self.response()
    self.checksum_matches(
        font_data, response[PATCHED_CHECKSUM],
        self.conform_message(
            "conform-response-patched-checksum",
            f"patched_checksum must be set to {fast_hash.compute(font_data)}"))

  def original_checksum_matches(self, font_data):
    response = self.response()
    self.checksum_matches(
        font_data, response[ORIGINAL_FONT_CHECKSUM],
        self.conform_message(
            "conform-response-original-checksum",
            f"original_checksum must be set to {fast_hash.compute(font_data)}"))

  def font_has_at_least_codepoints(self, font_data, subset):
    """Checks that the font represented by font_data has at least the codepoints in set subset."""
    all_codepoints = font_util.codepoints(font_data)
    self.test_case.assertTrue(
        subset.issubset(all_codepoints),
        self.conform_message(
            "conform-response-subset",
            f"Subset produced by patch must contain at "
            f"least {subset}, but contains {all_codepoints}"))

  def checksum_matches(self, data, expected_checksum, failure_message):
    self.test_case.assertEqual(fast_hash.compute(data), expected_checksum,
                               failure_message)

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
        self.test_case.assertEqual(
            result.returncode, 0,
            self.conform_message(
                "conform-response-valid-patch",
                f"Unable to decode patch, expected to be"
                f"in format {patch_format}"))
        return subset_file.read()
    else:
      self.test_case.fail(f"Unsupported patch_format {patch_format}")
      return None
