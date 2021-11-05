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
    req = urllib.request.Request("%s%s" % (self.server_address, path),
                                 data=data)
    return urllib.request.build_opener(IgnoreHttpErrors).open(req)

  ### Test Methods ###

  def test_accepts_well_formed_request(self):
    response = self.request(self.font_path, data=None)
    # TODO(garretrieger): send actual valid request, including magic number.
    # TODO(garretrieger): GET and POST
    self.assertEqual(response.status, 200, response.url)

  def test_rejects_not_found_font(self):
    # TODO(garretrieger): request data should be wellformed.
    response = self.request("/notfound", data=None)
    self.assertNotEqual(response.status, 200, response.url)


if __name__ == '__main__':
  if len(sys.argv) != 3:
    print_usage()
    sys.exit()

  font_path = sys.argv[2]
  del sys.argv[2]
  server_address = sys.argv[1]
  del sys.argv[1]

  unittest.main()
