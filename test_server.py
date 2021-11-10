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
from response_checker import ResponseChecker
from sample_requests import ValidRequests


def print_usage():
  print("python3 test_server.py <server address> <valid font path>")


class IgnoreHttpErrors(urllib.request.HTTPErrorProcessor):
  """Disables HTTP error handling in urllib: no redirects, no throwing."""

  def http_response(self, request, response):
    return response

  https_response = http_response


class ServerConformanceTest(unittest.TestCase):
  """Patch Subset Server conformance test."""

  def setUp(self):
    self.server_address = server_address
    self.font_path = font_path

  def tearDown(self):
    pass

  def request(self, path, data):
    if data is not None:
      headers = {
          "Content-Type": "application/binary",
      }
    else:
      headers = {}
    req = urllib.request.Request(f"{self.server_address}{path}",
                                 headers=headers,
                                 data=data)
    return ResponseChecker(
        self,
        urllib.request.build_opener(IgnoreHttpErrors).open(req))

  ### Test Methods ###

  # TODO(garretrieger): consider writing a parameterized tests against the set of all valid
  #                     requests. Plus individual tests as needed to check special cases.

  # TODO(garretrieger): test for GET.
  def test_minimal_request_post(self):
    response = self.request(self.font_path,
                            data=ValidRequests.MINIMAL_REQUEST)
    response.successful_response_checks()


if __name__ == '__main__':
  if len(sys.argv) != 3:
    print_usage()
    sys.exit()

  font_path = sys.argv[2]
  del sys.argv[2]
  server_address = sys.argv[1]
  del sys.argv[1]

  unittest.main()
