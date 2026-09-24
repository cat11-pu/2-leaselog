"""leaselog.py：租约内核（基线：只有内存态，无持久化与 fencing）。"""
from __future__ import annotations


class LeaseLog:
    def __init__(self):
        self.holder = ""
        self.expiry = 0
        self.epoch = 0
        self.grants = 0
        self.rejected = 0

    def grant(self, holder, ttl, now):
        self.holder = holder
        self.expiry = now + ttl
        self.epoch = 1
        self.grants += 1
        return self.epoch

    def valid(self, now):
        return bool(self.holder) and self.expiry > now

    def check(self, holder, token, now):
        """写请求校验：基线只看持有者。"""
        if self.valid(now) and holder == self.holder:
            return True
        self.rejected += 1
        return False

    def dump(self) -> bytes:
        raise NotImplementedError("落盘还没实现")

    def load(self, blob: bytes) -> int:
        raise NotImplementedError("恢复还没实现")
