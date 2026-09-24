"""leaselog.py：租约内核（单调 epoch、fencing、JSONL 落盘与重放）。"""
from __future__ import annotations

import json


class LeaseLog:
    def __init__(self):
        self.holder = ""
        self.expiry = 0
        self.epoch = 0
        self.grants = 0
        self.rejected = 0
        self.truncated = 0
        self._records = []

    def grant(self, holder, ttl, now):
        self.holder = holder
        self.expiry = now + ttl
        self.epoch += 1
        self.grants += 1
        self._records.append({
            "op": "grant",
            "holder": holder,
            "expiry": self.expiry,
            "epoch": self.epoch,
        })
        return self.epoch

    def renew(self, holder, ttl, now):
        """续租：只延长租期，不动 epoch。"""
        if not self.valid(now) or holder != self.holder:
            self.rejected += 1
            return False
        self.expiry = now + ttl
        self._records.append({
            "op": "renew",
            "holder": holder,
            "expiry": self.expiry,
            "epoch": self.epoch,
        })
        return True

    def valid(self, now):
        return bool(self.holder) and self.expiry > now

    def check(self, holder, token, now):
        """写请求校验：fencing token + 持有者 + 租期，失败计入 rejected。"""
        if not self.valid(now):
            self.rejected += 1
            return False
        if holder != self.holder:
            self.rejected += 1
            return False
        if token is not None and token < self.epoch:
            self.rejected += 1
            return False
        return True

    def record_write(self, holder, value, now):
        """登记一条已接受的写，随 dump 落盘。"""
        self._records.append({
            "op": "write",
            "holder": holder,
            "value": value,
            "at": now,
            "epoch": self.epoch,
        })

    def dump(self) -> bytes:
        """JSONL：授予/续租/写记录 + 末尾一条 checkpoint 快照。"""
        records = list(self._records)
        records.append({
            "op": "checkpoint",
            "holder": self.holder,
            "expiry": self.expiry,
            "epoch": self.epoch,
            "grants": self.grants,
        })
        lines = [json.dumps(rec, sort_keys=True) for rec in records]
        return ("\n".join(lines) + "\n").encode("utf-8")

    def load(self, blob: bytes) -> int:
        """重放 JSONL，返回重放条数；尾部半条记录忽略并计入 truncated。"""
        replayed = 0
        lines = blob.split(b"\n")
        if lines and lines[-1] == b"":
            lines.pop()
        elif lines:
            self.truncated += 1
            lines.pop()
        for raw in lines:
            if not raw.strip():
                continue
            try:
                rec = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self.truncated += 1
                continue
            self._replay(rec)
            replayed += 1
        return replayed

    def _replay(self, rec):
        op = rec.get("op")
        if op == "grant":
            self.holder = rec["holder"]
            self.expiry = rec["expiry"]
            self.epoch = max(self.epoch, rec["epoch"])
            self.grants += 1
        elif op == "renew":
            self.holder = rec["holder"]
            self.expiry = rec["expiry"]
            self.epoch = max(self.epoch, rec["epoch"])
        elif op == "checkpoint":
            self.holder = rec["holder"]
            self.expiry = rec["expiry"]
            self.epoch = max(self.epoch, rec["epoch"])
            self.grants = max(self.grants, rec.get("grants", 0))
        self._records.append(rec)
