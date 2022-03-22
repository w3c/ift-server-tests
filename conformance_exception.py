"""Exception raised when a conformance statement is violated."""


class ConformanceException(Exception):

  def __init__(self, message, conformance_id):
    super().__init__(message)
    self.conformance_id = conformance_id
