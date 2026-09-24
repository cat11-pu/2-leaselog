"""writer.py：写入门面（老接口：不带 token 的 commit 继续可用）。"""
from __future__ import annotations

from leaselog import LeaseLog


class Writer:
    def __init__(self, log: LeaseLog):
        self.log = log
        # 从日志重放已接受的写，崩溃恢复后接受数不回退。
        self.accepted = log.accepted_writes
        self.data = {}
        for rec in log.writes:
            self.data["v"] = rec["value"]

    def commit(self, holder, value, now, token=None):
        """带 token 走 fencing；不带 token 的老写法仍然可用。"""
        if not self.log.check(holder, token, now):
            return False
        self.log.record_write(holder, value, now, token)
        self.accepted += 1
        self.data["v"] = value
        return True
