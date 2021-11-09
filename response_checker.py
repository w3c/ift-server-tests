"""
Helper for checking common cases on incremental font transfer server responses.
"""


class ResponseChecker:
  """Defines a set of common checks against a IFT server response."""

  def __init__(self, test_case, response):
    self.test_case = test_case
    self.status_code = response.status
    self.response_data = response.read()
    self.url = response.url

  def successful_response_checks(self):
    self.test_case.assertEqual(self.status_code, 200, self.url)
    self.test_case.assertEqual(self.response_data[:4], [0x49, 0x46, 0x54, 0x20],
                               self.url)
