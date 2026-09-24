"""leaselog.py：租约内核（单调 epoch、fencing、JSON-lines 落盘与重放）。"""
from __future__ import annotations

import json


class LeaseLog:
    def __init__(self):
        self.holder = ""
        self.expiry = 0
        self.epoch = 0
        self.grants = 0
        self.rejected = 0
        self.accepted = 0
        self.truncated = 0
        self.records = []

    def grant(self, holder, ttl, now):
        self.holder = holder
        self.expiry = now + ttl
        self.epoch += 1
        self.grants += 1
        self.records.append({
            "kind": "grant",
            "holder": holder,
            "expiry": self.expiry,
            "epoch": self.epoch,
        })
        return self.epoch

    def valid(self, now):
        return bool(self.holder) and self.expiry > now

    def renew(self, ttl, now):
        """续租：只延长租期，epoch 保持不变。"""
        if not self.valid(now):
            return False
        self.expiry = now + ttl
        self.records.append({
            "kind": "renew",
            "holder": self.holder,
            "expiry": self.expiry,
            "epoch": self.epoch,
        })
        return True

    def check(self, holder, token, now):
        """写请求校验：fencing token、持有者、租期三者都过才放行。"""
        if not self.valid(now) or holder != self.holder:
            self.rejected += 1
            return False
        if token is not None and token < self.epoch:
            self.rejected += 1
            return False
        return True

    def record_write(self, holder, value, now, token):
        """登记一条已接受的写（供落盘重放）。"""
        self.accepted += 1
        self.records.append({
            "kind": "write",
            "holder": holder,
            "value": value,
            "at": now,
            "token": token,
        })

    def dump(self) -> bytes:
        state = {
            "kind": "state",
            "holder": self.holder,
            "expiry": self.expiry,
            "epoch": self.epoch,
            "grants": self.grants,
            "rejected": self.rejected,
            "accepted": self.accepted,
        }
        lines = [state] + self.records
        return "".join(
            json.dumps(line, sort_keys=True) + "\n" for line in lines
        ).encode("utf-8")

    def load(self, blob: bytes) -> int:
        """重放落盘记录，返回成功重放条数；尾部半条记录忽略并计入 truncated。"""
        replayed = 0
        for raw in blob.split(b"\n"):
            if not raw:
                continue
            try:
                entry = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self.truncated += 1
                break
            kind = entry.get("kind")
            if kind == "state":
                self.holder = entry["holder"]
                self.expiry = entry["expiry"]
                self.epoch = max(self.epoch, entry["epoch"])
                self.grants = entry["grants"]
                self.rejected = entry["rejected"]
                self.accepted = entry["accepted"]
            elif kind == "grant":
                self.epoch = max(self.epoch, entry["epoch"])
                self.records.append(entry)
            elif kind == "renew":
                self.expiry = max(self.expiry, entry["expiry"])
                self.records.append(entry)
            elif kind == "write":
                self.records.append(entry)
            replayed += 1
        return replayed
