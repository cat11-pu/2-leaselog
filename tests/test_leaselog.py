import unittest

from leaselog import LeaseLog
from writer import Writer


class TestLease(unittest.TestCase):
    def test_grant_and_valid(self):
        log = LeaseLog()
        log.grant("c1", 10, 0)
        self.assertTrue(log.valid(5))

    def test_expired(self):
        log = LeaseLog()
        log.grant("c1", 10, 0)
        self.assertFalse(log.valid(10))

    def test_check_holder(self):
        log = LeaseLog()
        log.grant("c1", 10, 0)
        self.assertTrue(log.check("c1", None, 5))
        self.assertFalse(log.check("c2", None, 5))

    def test_writer_commit(self):
        log = LeaseLog()
        log.grant("c1", 10, 0)
        writer = Writer(log)
        self.assertTrue(writer.commit("c1", "x", 5))

    def test_rejected_counter(self):
        log = LeaseLog()
        log.check("c2", None, 0)
        self.assertEqual(log.rejected, 1)


if __name__ == "__main__":
    unittest.main()
