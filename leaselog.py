"""leaselog.py：租约内核（内存态 + JSON Lines 落盘 + fencing）。"""
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
        self.records = []

    def grant(self, holder, ttl, now):
        self.holder = holder
        self.expiry = now + ttl
        self.epoch += 1
        self.grants += 1
        self.records.append({
            "op": "grant",
            "holder": holder,
            "expiry": self.expiry,
            "epoch": self.epoch,
        })
        return self.epoch

    def valid(self, now):
        return bool(self.holder) and self.expiry > now

    def check(self, holder, token, now):
        """fencing：过期、持有者不符、或 token 落后于当前 epoch，一律拒绝。"""
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

    def log_write(self, holder, value, now):
        """登记一条已接受的写，随 dump 落盘。"""
        self.records.append({
            "op": "write",
            "holder": holder,
            "value": value,
            "epoch": self.epoch,
            "at": now,
        })

    def dump(self) -> bytes:
        meta = {
            "op": "meta",
            "epoch": self.epoch,
            "grants": self.grants,
            "rejected": self.rejected,
        }
        lines = [json.dumps(meta, sort_keys=True)]
        lines += [json.dumps(rec, sort_keys=True) for rec in self.records]
        return ("\n".join(lines) + "\n").encode("utf-8")

    def load(self, blob: bytes) -> int:
        text = blob.decode("utf-8", errors="replace")
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        elif lines:
            # 尾部没有换行符：半条撕裂记录，忽略并计数
            lines.pop()
            self.truncated += 1
        replayed = 0
        for line in lines:
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                self.truncated += 1
                continue
            self._replay(rec)
            replayed += 1
        return replayed

    def _replay(self, rec):
        op = rec.get("op")
        if op == "meta":
            self.epoch = max(self.epoch, int(rec.get("epoch", 0)))
            self.grants = max(self.grants, int(rec.get("grants", 0)))
            self.rejected = max(self.rejected, int(rec.get("rejected", 0)))
            return
        if op == "grant":
            self.holder = rec.get("holder", self.holder)
            self.expiry = max(self.expiry, int(rec.get("expiry", 0)))
            self.epoch = max(self.epoch, int(rec.get("epoch", 0)))
        self.records.append(rec)
