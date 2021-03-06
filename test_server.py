"""
Usage
python3 test_server.py <server address> <valid font path>

Tests the conformance of a server at the specified address with the incremental font transfer
specification.

https://w3c.github.io/IFT/Overview.htm

Server address is the address for a http server that supports patch subset.
Valid font path Is a path which can be used to incrementally transfer a font on the provided
patch subset server.
"""

import unittest

import urllib.request
import sys

from base64 import urlsafe_b64encode
from conformance_exception import ConformanceException
from response_checker import PATCH
from response_checker import VCDIFF
from response_checker import ResponseChecker
from sample_requests import ValidRequests
import axis_util
import fast_hash
import font_util
import integer_list


def print_usage():
  print(
      "python3 test_server.py <server host> <request path> <original font file>\n"
      "\n"
      "If the original font file is a variable font, then additional tests specific "
      "to the servers handling of variable fonts will be run in addition to the regular "
      "conformance tests.")


class IgnoreHttpErrors(urllib.request.HTTPErrorProcessor):
  """Disables HTTP error handling in urllib: no redirects, no throwing."""

  def http_response(self, request, response):
    return response

  https_response = http_response


# pylint: disable=too-many-public-methods
class ServerConformanceTest(unittest.TestCase):
  """Patch Subset Server conformance test."""

  METHODS = ["GET", "POST"]

  def setUp(self):
    self.server_address = server_address
    self.request_path = request_path
    with open(font_file_path, "rb") as font:
      self.original_font_bytes = font.read()

  def tearDown(self):
    pass

  def request(self, path, data, method="POST"):
    """Send a HTTP request to path."""
    is_post = (method == "POST")
    if is_post:
      headers = {
          "Content-Type": "application/binary",
      }
    else:
      headers = {}

    if is_post:
      req = urllib.request.Request(f"https://{self.server_address}{path}",
                                   headers=headers,
                                   data=data)
    else:
      base64_data = urlsafe_b64encode(data).decode("utf-8")
      req = urllib.request.Request(
          f"https://{self.server_address}{path}?request={base64_data}",
          headers=headers)

    return ResponseChecker(
        self,
        urllib.request.build_opener(IgnoreHttpErrors).open(req),
        self.original_font_bytes)

  def next_available_codepoint(self, base_codepoints):
    """Finds a codepoint that's in the original font, but not in base_codepoints."""
    all_codepoints = font_util.codepoints(self.original_font_bytes)
    for codepoint in sorted(all_codepoints.difference(base_codepoints)):
      if codepoint >= 0x30:
        return codepoint
    raise AssertionError("No codepoint is available to request.")

  ### Test Methods ###

  def test_integer_list_decode_matches_spec(self):
    # Tests that our integer list decode implementation matches the spec.
    values = integer_list.decode(
        bytes([0x2E, 0x28, 0x3D, 0x11, 0x81, 0x00, 0x02, 0x02, 0x81, 0x09]))
    self.assertEqual(values, [23, 43, 12, 3, 67, 68, 69, 0])

    self.assertRaises(ConformanceException, integer_list.decode,
                      bytes([0x80, 0x01]))
    self.assertRaises(ConformanceException, integer_list.decode,
                      bytes([0x81, 0x80, 0x80, 0x80, 0x80, 0x00]))
    self.assertRaises(ConformanceException, integer_list.decode,
                      bytes([0xFF, 0xFF, 0xFF, 0xFF, 0x01]))

  def test_our_hash_matches_spec(self):
    # Tests that our hash implementation matches the spec.
    # Test cases from: https://w3c.github.io/IFT/Overview.html#computing-checksums
    self.assertEqual(fast_hash.compute(bytes([0x0f, 0x7b, 0x5a, 0xe5])),
                     0xe5e0d1dc89eaa189)
    self.assertEqual(
        fast_hash.compute(
            bytes([
                0x1d, 0xf4, 0x02, 0x5e, 0xd3, 0xb8, 0x43, 0x21, 0x3b, 0xae, 0xde
            ])), 0xb31e9c70768205fb)

  def test_axis_space_equals(self):
    space_1 = {
        b"wght": [{
            0: 400
        }],
        b"wdth": [{
            0: 300
        }, {
            0: 100,
            1: 200
        }],
    }
    space_2 = {
        b"wdth": [{
            0: 100,
            1: 200
        }, {
            0: 300
        }],
        b"wght": [{
            0: 400,
            1: 400
        }],
    }
    space_3 = {
        b"wght": [{
            0: 400
        }],
    }
    space_4 = {
        b"wght": [{
            0: 500
        }],
    }
    space_5 = {
        b"wght": [{
            0: 400
        }],
        b"wdth": [{
            0: 300
        }, {
            0: 100,
            1: 205
        }],
    }
    space_6 = {
        b"ital": [{
            0: 400
        }],
        b"wdth": [{
            0: 300
        }, {
            0: 100,
            1: 200
        }],
    }

    self.assertTrue(axis_util.axis_space_equal(space_1, space_2))
    self.assertFalse(axis_util.axis_space_equal(space_1, space_3))
    self.assertFalse(axis_util.axis_space_equal(space_3, space_4))
    self.assertFalse(axis_util.axis_space_equal(space_1, space_5))
    self.assertFalse(axis_util.axis_space_equal(space_1, space_6))

  # TODO(garretrieger):
  # Mising tests:
  # - Supports range requests.
  def test_minimal_request(self):
    for method in ServerConformanceTest.METHODS:
      with self.subTest(msg=f"{method} request."):
        response = self.request(self.request_path,
                                data=ValidRequests.MINIMAL_REQUEST,
                                method=method)

        response.successful_response_checks()
        response.has_codepoint_mapping()
        response.format_in({VCDIFF})
        subset_bytes = response.check_apply_patch_to({0x41})

        original_axis_space = font_util.axis_space(self.original_font_bytes)
        subset_axis_space = font_util.axis_space(subset_bytes)
        if original_axis_space:
          response.original_axis_space_is(original_axis_space)
          response.subset_axis_space_is(subset_axis_space)

        response.print_tested_ids()

  def test_unrecognized_format(self):
    response = self.request(self.request_path,
                            data=ValidRequests.UNRECOGNIZED_FORMAT,
                            method="GET")

    response.successful_response_checks()
    response.has_codepoint_mapping()
    response.format_in({VCDIFF})
    response.check_apply_patch_to({0x41})
    response.tested("conform-response-ignore-unrecognized-formats")
    response.print_tested_ids()

  def test_ignores_unrecognized_fields(self):
    for method in ServerConformanceTest.METHODS:
      with self.subTest(msg=f"{method} request."):
        response = self.request(self.request_path,
                                data=ValidRequests.MINIMAL_REQUEST_EXTRA_FIELDS,
                                method=method)

        response.successful_response_checks()
        response.tested("conform-object-unrecognized-field")
        response.print_tested_ids()

  def test_minimal_sparse_set_request(self):
    for method in ServerConformanceTest.METHODS:
      with self.subTest(msg=f"{method} request."):
        response = self.request(
            self.request_path,
            data=ValidRequests.MINIMAL_SPARSE_BIT_SET_REQUEST,
            method=method)

        response.successful_response_checks()
        response.has_codepoint_mapping()
        response.format_in({VCDIFF})
        response.check_apply_patch_to(set(range(0x41, 0x61)))
        response.print_tested_ids()

  def test_minimal_combined_set_request(self):
    for method in ServerConformanceTest.METHODS:
      with self.subTest(msg=f"{method} request."):
        response = self.request(self.request_path,
                                data=ValidRequests.MINIMAL_COMBINED_SET_REQUEST,
                                method=method)

        response.successful_response_checks()
        response.has_codepoint_mapping()
        response.format_in({VCDIFF})
        expected = set(range(0x41, 0x61))
        expected.add(0x65)
        response.check_apply_patch_to(expected)
        response.print_tested_ids()

  def test_unrecognized_codepoint_reordering(self):
    init_response = self.request(self.request_path,
                                 method="GET",
                                 data=ValidRequests.MINIMAL_REQUEST)

    codepoint_map = init_response.codepoint_mapping()
    base_codepoints = init_response.codepoints_in_response()
    next_cp = self.next_available_codepoint(base_codepoints)
    request_generator = lambda data: self.request(
        self.request_path, method="GET", data=data)
    patch_response = init_response.extend(request_generator, {next_cp},
                                          codepoint_map=codepoint_map,
                                          override_reordering_checksum=12345)

    patch_response.has_codepoint_mapping()
    patch_response.successful_response_checks()
    patch_response.not_patch_or_replacement()
    patch_response.print_tested_ids()

  def test_minimal_patch_request(self):
    for method in ServerConformanceTest.METHODS:
      for remap_codepoints in [False, True]:
        with self.subTest(msg=f"{method} request."):

          init_response = self.request(self.request_path,
                                       method=method,
                                       data=ValidRequests.MINIMAL_REQUEST)

          init_response.has_codepoint_mapping()
          codepoint_map = init_response.codepoint_mapping(
          ) if remap_codepoints else None
          base_codepoints = init_response.codepoints_in_response()
          next_cp = self.next_available_codepoint(base_codepoints)
          request_generator = lambda data, m=method: self.request(
              self.request_path, method=m, data=data)
          patch_response = init_response.extend(request_generator, {next_cp},
                                                codepoint_map=codepoint_map)

          if PATCH not in patch_response.response():
            print(
                "WARNING(test_minimal_patch_request_post): expected response to be a patch."
            )

          additional_ids = [
              "conform-remap-codepoints-have", "conform-remap-codepoints-needed"
          ] if remap_codepoints else None
          base_codepoints.add(next_cp)
          patch_response.successful_response_checks()
          patch_response.format_in({VCDIFF})
          patch_response.check_apply_patch_to(
              base_codepoints, additional_conformance_ids=additional_ids)
          patch_response.print_tested_ids()

  def test_patch_request_incorrect_original_font_checksum(self):
    """Checks that a bad original font checksum is handled without error."""
    method = "GET"
    with self.subTest(msg=f"{method} request."):

      init_response = self.request(self.request_path,
                                   method=method,
                                   data=ValidRequests.MINIMAL_REQUEST)

      base_codepoints = init_response.codepoints_in_response()
      next_cp = self.next_available_codepoint(base_codepoints)
      request_generator = lambda data, m=method: self.request(
          self.request_path, method=m, data=data)
      patch_response = init_response.extend(request_generator, {next_cp},
                                            override_original_checksum=1234)

      base_codepoints.add(next_cp)
      patch_response.successful_response_checks()
      patch_response.format_in({VCDIFF})
      patch_response.check_apply_patch_to(base_codepoints)
      patch_response.print_tested_ids()

  def test_patch_request_incorrect_base_checksum(self):
    """Checks that a bad base checksum is handled without error."""
    method = "GET"
    with self.subTest(msg=f"{method} request."):

      init_response = self.request(self.request_path,
                                   method=method,
                                   data=ValidRequests.MINIMAL_REQUEST)

      base_codepoints = init_response.codepoints_in_response()
      next_cp = self.next_available_codepoint(base_codepoints)
      request_generator = lambda data, m=method: self.request(
          self.request_path, method=m, data=data)
      patch_response = init_response.extend(request_generator, {next_cp},
                                            override_base_checksum=1234)

      base_codepoints.add(next_cp)
      patch_response.successful_response_checks()
      patch_response.format_in({VCDIFF})
      patch_response.check_apply_patch_to(base_codepoints)
      patch_response.print_tested_ids()

  def test_rejects_malformed_request(self):
    response = self.request(self.request_path,
                            data=ValidRequests.MALFORMED_REQUEST,
                            method="GET")
    response.is_error_400()
    response.print_tested_ids()

  def test_rejects_malformed_version_request(self):
    response = self.request(self.request_path,
                            data=ValidRequests.MALFORMED_VERSION_REQUEST,
                            method="GET")
    response.is_error_400("conform-request-protocol-version")
    response.print_tested_ids()

  def test_rejects_malformed_ordering_checksum_request(self):
    response = self.request(
        self.request_path,
        data=ValidRequests.MALFORMED_ORDERING_CHECKSUM_REQUEST,
        method="GET")
    response.is_error_400("conform-request-ordering-checksum")
    response.print_tested_ids()

  def test_rejects_malformed_base_checksum_request(self):
    response = self.request(self.request_path,
                            data=ValidRequests.MALFORMED_BASE_CHECKSUM_REQUEST,
                            method="GET")
    response.is_error_400("conform-request-base-checksum")
    response.print_tested_ids()

  def test_rejects_malformed_integer_list_request(self):
    response = self.request(self.request_path,
                            data=ValidRequests.MALFORMED_INTEGER_LIST_REQUEST,
                            method="GET")
    response.is_error_400("conform-sorted-integer-list-rejects-illegal")
    response.print_tested_ids()


if __name__ == '__main__':
  if len(sys.argv) != 4:
    print_usage()
    sys.exit()

  font_file_path = sys.argv[3]
  del sys.argv[3]
  request_path = sys.argv[2]
  del sys.argv[2]
  server_address = sys.argv[1]
  del sys.argv[1]

  unittest.main()
