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
from response_checker import PATCH
from response_checker import VCDIFF
from response_checker import ResponseChecker
from sample_requests import ValidRequests
import fast_hash
import font_util


def print_usage():
  print(
      "python3 test_server.py <server host> <request path> <original font file>"
  )


class IgnoreHttpErrors(urllib.request.HTTPErrorProcessor):
  """Disables HTTP error handling in urllib: no redirects, no throwing."""

  def http_response(self, request, response):
    return response

  https_response = http_response


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

  # TODO(garretrieger): consider writing a parameterized tests against the set of all valid
  #                     requests. Plus individual tests as needed to check special cases.

  # TODO(garretrieger): additional tests:
  # - patch request, using previously provided codepoint ordering.
  # - patch request, mixing indices and codepoints.
  # - patch request, not using previously providing codepoint ordering.
  # - patch request, with invalid codepoint ordering.
  # - patch request, bad original font checksum
  # - patch request, bad base checksum
  # - requests which uses sparse bit sets
  def test_minimal_request(self):
    for method in ServerConformanceTest.METHODS:
      with self.subTest(msg=f"{method} request."):
        response = self.request(self.request_path,
                                data=ValidRequests.MINIMAL_REQUEST,
                                method=method)

        response.successful_response_checks()
        response.assert_has_codepoint_mapping()
        response.format_in({VCDIFF})
        response.check_apply_patch_to({0x41})
        response.print_tested_ids()

  def test_minimal_patch_request(self):
    for method in ServerConformanceTest.METHODS:
      for remap_codepoints in {False, True}:
        with self.subTest(msg=f"{method} request."):

          init_response = self.request(self.request_path,
                                       method=method,
                                       data=ValidRequests.MINIMAL_REQUEST)

          codepoint_map = init_response.codepoint_mapping() if remap_codepoints else None
          base_codepoints = init_response.codepoints_in_response()
          next_cp = self.next_available_codepoint(base_codepoints)
          request_generator = lambda data: self.request(self.request_path, method=method, data=data)
          patch_response = init_response.extend(request_generator,
                                                {next_cp},
                                                codepoint_map=codepoint_map)

          if PATCH not in patch_response.response():
            print(
                "WARNING(test_minimal_patch_request_post): expected response to be a patch."
            )

          base_codepoints.add(next_cp)
          patch_response.successful_response_checks()
          patch_response.format_in({VCDIFF})
          patch_response.check_apply_patch_to(base_codepoints)
          patch_response.print_tested_ids()


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
