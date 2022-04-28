"""
Helper for checking common cases on incremental font transfer server responses.
"""

import subprocess
import tempfile

from cbor2 import loads
import axis_util
import font_util
import fast_hash
from sample_requests import ValidRequests
import integer_list
from conformance_exception import ConformanceException
import shaping_check

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
  """Returns a link to conformance id(s) tag."""
  if isinstance(tag, list):
    return ",\n".join(
        [f"https://w3c.github.io/IFT/Overview.html#{t}" for t in tag])
  return f"https://w3c.github.io/IFT/Overview.html#{tag}"


# pylint: disable=too-many-public-methods
class ResponseChecker:
  """Defines a set of common checks against a IFT server response."""

  # pylint: disable=too-many-instance-attributes
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
    """Message to print on failed conformance to requirement 'tag'."""
    self.tested(tag)
    return (f"Failed requirement {spec_link(tag)}\n"
            f"  {message}\n"
            f"  Request URL: {self.url}")

  def tested(self, tag):
    """Adds tag(s) to the list of tested ids."""
    if isinstance(tag, list):
      self.tested_ids.update(tag)
    else:
      self.tested_ids.add(tag)

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

  def original_axis_space(self):
    response = self.response()
    self.axis_space_well_formed(response[ORIGINAL_AXIS_SPACE])
    return response[ORIGINAL_AXIS_SPACE]

  def original_axis_space_is(self, axis_space):
    """Asserts the response sets original axis space and it's equal to axis_space."""
    self.test_case.assertTrue(
        ORIGINAL_AXIS_SPACE in self.response(),
        self.conform_message("conform-response-original-axis-space",
                             "original_axis_space must be set."))
    self.test_case.assertTrue(
        axis_util.axis_space_equal(self.original_axis_space(), axis_space),
        self.conform_message(
            "conform-response-original-axis-space",
            f"original_axis_space must be set to the axis "
            f"space of the original font "
            f"{axis_space} != {self.original_axis_space()}"))

  def subset_axis_space(self):
    response = self.response()
    self.axis_space_well_formed(response[SUBSET_AXIS_SPACE])
    return response[SUBSET_AXIS_SPACE]

  def subset_axis_space_is(self, axis_space):
    """Asserts the response sets subset axis space and it's equal to axis_space."""
    self.test_case.assertTrue(
        SUBSET_AXIS_SPACE in self.response(),
        self.conform_message("conform-response-subset-axis-space",
                             "subset_axis_space must be set."))
    self.test_case.assertTrue(
        axis_util.axis_space_equal(self.subset_axis_space(), axis_space),
        self.conform_message(
            "conform-response-subset-axis-space",
            f"subset_axis_space must be set to the axis "
            f"space of the subset font "
            f"{axis_space} != {self.subset_axis_space()}"))

  def axis_space_well_formed(self, space):
    """Tests if the provided axis space is well-formed according to the spec."""
    # interval lists are disjoint.
    for intervals in space.values():
      for interval in intervals:
        self.axis_interval_well_formed(interval)

      sorted_intervals = sorted(
          intervals, key=lambda interval: interval[axis_util.AXIS_START])
      if len(sorted_intervals) <= 1:
        self.tested("conform-axis-space-disjoint")
        return

      for i in range(len(sorted_intervals) - 1):
        interval = sorted_intervals[i]
        next_interval = sorted_intervals[i + 1]
        self.test_case.assertLess(
            interval[axis_util.AXIS_END], next_interval[axis_util.AXIS_START],
            self.conform_message("conform-axis-space-disjoint",
                                 "AxisInterval.start must be set."))

  def axis_interval_well_formed(self, interval):
    """Tests if the provided axis interval is well-formed according to the spec."""
    # start is set.
    # end is not set or >= start.
    self.test_case.assertTrue(
        axis_util.AXIS_START in interval,
        self.conform_message("conform-axis-interval-start",
                             "AxisInterval.start must be set."))

    if axis_util.AXIS_END not in interval:
      self.tested("conform-axis-interval-end")
      return

    self.test_case.assertGreater(
        interval[axis_util.AXIS_END], interval[axis_util.AXIS_START],
        self.conform_message("conform-axis-interval-end",
                             "AxisInterval.end must be greater than start."))

  def is_error_400(self, extra_tag=None):
    """Checks that the response has status code 400."""
    tags = ["conform-reject-malformed-request"]
    if extra_tag:
      tags.append(extra_tag)
    self.test_case.assertEqual(
        self.status_code, 400,
        self.conform_message(tags, "Status code must indicate failure (400)"))

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

  def check_apply_patch_to(self,
                           min_codepoints,
                           additional_conformance_ids=None):
    """Checks that this response can be applied to base and covers at least min_codepoints."""
    response = self.response()

    base = self.base
    if REPLACEMENT in response:
      base = bytes([])
      patch = response[REPLACEMENT]
    else:
      patch = response[PATCH]

    subset = self.decode_patch(base, patch, response[PATCH_FORMAT])
    self.font_has_at_least_codepoints(
        subset,
        min_codepoints,
        additional_conformance_ids=additional_conformance_ids)
    self.patched_checksum_matches(subset)

    # If we got this far and the format was VCDIFF that we can confirm the server supports
    # VCDIFF
    self.tested("conform-vcdiff")

    # TODO(garretrieger): font shapes identical to original for subset codepoints.
    return subset

  # pylint: disable=too-many-arguments
  def extend(self,
             requester,
             new_codepoints,
             codepoint_map=None,
             override_reordering_checksum=None,
             override_original_checksum=None,
             override_base_checksum=None):
    """Make a second request that extends the font fetched by this one."""
    base = self.check_apply_patch_to(set())
    base_checksum = (fast_hash.compute(base) if override_base_checksum is None
                     else override_base_checksum)
    original_checksum = (self.original_font_checksum()
                         if override_original_checksum is None else
                         override_original_checksum)
    base_codepoints = self.codepoints_in_response()
    ordering_checksum = self.ordering_checksum(
    ) if codepoint_map is not None else None
    if override_reordering_checksum is not None:
      ordering_checksum = override_reordering_checksum

    if codepoint_map:
      base_codepoints = {codepoint_map[cp] for cp in base_codepoints}
      new_codepoints = {codepoint_map[cp] for cp in new_codepoints}

    request_cbor = ValidRequests.minimal_patch_request(base_codepoints,
                                                       new_codepoints,
                                                       original_checksum,
                                                       base_checksum,
                                                       ordering_checksum)

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

  def has_codepoint_mapping(self):
    """Tests if the response contains a codepoint mapping."""
    self.test_case.assertTrue(
        CODEPOINT_ORDERING in self.response(),
        self.conform_message("conform-response-codepoint-ordering",
                             "codepoint_ordering must be set."))

    mapping = self.codepoint_mapping()
    original_cps = font_util.codepoints(self.original_font_bytes)
    for codepoint in original_cps:
      self.test_case.assertTrue(
          codepoint in mapping,
          self.conform_message(
              "conform-remap-all",
              f"All codepoints in the original font must be "
              f"in the codepoint reordering. {codepoint} is missing."))
    return self

  def not_patch_or_replacement(self):
    """Tests that this response contains neither patch nor replacement data."""
    self.test_case.assertFalse(
        PATCH in self.response() or REPLACEMENT in self.response(),
        self.conform_message("conform-bad-reordering",
                             "Neither patch nor replacement may be set."))

  def codepoint_mapping(self):
    """Decodes and returns the codepoint mapping in the response."""
    response = self.response()
    try:
      mapping_list = integer_list.decode(response[CODEPOINT_ORDERING])
    except ConformanceException as err:
      self.test_case.assertTrue(
          False,
          self.conform_message(
              err.conformance_id, f"Conformance error decoding "
              f"codepoint_ordering: {err}"))

    return {cp: idx for idx, cp in enumerate(mapping_list)}

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
    """Attempts to decode the int_list to see if it's well formed."""
    maybe_err = None
    try:
      integer_list.decode(int_list)
    except ConformanceException as err:
      maybe_err = err

    self.test_case.assertTrue(
        maybe_err is None,
        self.conform_message(
            "conform-uintbase128-illegal", f"Conformance error decoding "
            f"codepoint_ordering: {maybe_err}"))

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

    if PATCH_FORMAT in response:
      self.test_case.assertTrue(
          response[PATCH_FORMAT] in PATCH_FORMATS,
          self.conform_message(
              "conform-response-valid-format",
              f"patch_format {response[PATCH_FORMAT]} not in {PATCH_FORMATS}."))

    self.test_case.assertTrue(
        not (bool(PATCH in response) and bool(REPLACEMENT in response)),
        self.conform_message("conform-response-patch-or-replacement",
                             "Only one of patch or replacement can be set."))

    if PATCH in response or REPLACEMENT in response:
      self.test_case.assertTrue(
          isinstance(response[PATCH_FORMAT], int),
          self.conform_message("conform-response-font-checksums",
                               "patch_format must be set."))
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

  def font_has_at_least_codepoints(self,
                                   font_data,
                                   subset,
                                   additional_conformance_ids=None):
    """Checks that the font represented by font_data has at least the codepoints in set subset."""
    tags = ["conform-response-subset"]
    if additional_conformance_ids is not None:
      tags.extend(additional_conformance_ids)

    all_codepoints = font_util.codepoints(font_data)
    self.test_case.assertTrue(
        subset.issubset(all_codepoints),
        self.conform_message(
            tags, f"Subset produced by patch must contain at "
            f"least {subset}, but contains {all_codepoints}"))

    self.test_case.assertTrue(
        shaping_check.identical_shaping(self.original_font_bytes, font_data,
                                        subset),
        self.conform_message(
            "conform-font-subset",
            "Generated font subset rendering is not identical "
            "to the original font."))

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
