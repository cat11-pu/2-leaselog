"""writer.py：写入门面（老接口 commit 不能改）。"""
from __future__ import annotations

from leaselog import LeaseLog


class Writer:
    def __init__(self, log: LeaseLog):
        self.log = log
        self.data = {}

    @property
    def accepted(self):
        return self.log.accepted

    def commit(self, holder, value, now, token=None):
        """老接口：不带 token 的写法必须继续可用。"""
        if not self.log.check(holder, token, now):
            return False
        self.log.record_write(holder, value, now, token)
        self.data["v"] = value
        return True
