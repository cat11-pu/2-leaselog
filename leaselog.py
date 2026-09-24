"""leaselog.py：租约内核（单调 epoch、fencing 校验、崩溃重放）。"""
from __future__ import annotations

import json
import struct

# 每一帧：4 字节大端长度前缀 + UTF-8 JSON 负载。
_PREFIX = struct.Struct(">I")
_HEADER = {"type": "init", "v": 1}


class LeaseLog:
    def __init__(self):
        self.holder = ""
        self.expiry = 0
        self.epoch = 0
        self.grants = 0
        self.rejected = 0
        self.accepted_writes = 0
        self.truncated = 0
        self.writes = []
        self._journal = []

    def grant(self, holder, ttl, now):
        # 每次授予（含过期后重新授予）都进入下一个 epoch。
        self.epoch += 1
        self.holder = holder
        self.expiry = now + ttl
        self.grants += 1
        self._journal.append(
            {"type": "grant", "holder": holder, "expiry": self.expiry, "epoch": self.epoch}
        )
        return self.epoch

    def renew(self, holder, ttl, now):
        """续租：只延长到期时刻，epoch 不变。"""
        if not (self.valid(now) and holder == self.holder):
            return False
        self.expiry = now + ttl
        return True

    def valid(self, now):
        return bool(self.holder) and self.expiry > now

    def check(self, holder, token, now):
        """fencing 校验：持有者不符、租期过期、token 落后于当前 epoch 一律拒绝。"""
        if self.valid(now) and holder == self.holder:
            if token is None or token >= self.epoch:
                return True
        self.rejected += 1
        return False

    def record_write(self, holder, value, now, token):
        """接受一次写，追加到内存日志，供 dump 落盘。"""
        rec = {
            "type": "write",
            "holder": holder,
            "value": value,
            "at": now,
            "token": token,
        }
        self._journal.append(rec)
        self.writes.append(rec)
        self.accepted_writes += 1

    @staticmethod
    def _frame(rec) -> bytes:
        payload = json.dumps(rec, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return _PREFIX.pack(len(payload)) + payload

    def dump(self) -> bytes:
        """落盘：头帧 + 授予/写记录帧，末尾带一条崩溃瞬间的半条记录。"""
        frames = [self._frame(_HEADER)]
        frames.extend(self._frame(rec) for rec in self._journal)
        blob = b"".join(frames)
        # 模拟崩溃时最后一条 write 只追加了一半（长度前缀声称的字节数没写全）。
        tail = json.dumps(
            {
                "type": "write",
                "holder": self.holder,
                "value": "x",
                "at": self.expiry,
                "token": self.epoch,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        blob += _PREFIX.pack(len(tail)) + tail[: len(tail) // 2]
        return blob

    def load(self, blob: bytes) -> int:
        """重放 blob，返回完整重放的帧条数；尾部半条记录忽略并计入 truncated。"""
        replayed = 0
        pos = 0
        total = len(blob)
        while pos < total:
            if total - pos < _PREFIX.size:
                self.truncated += 1
                break
            (length,) = _PREFIX.unpack_from(blob, pos)
            pos += _PREFIX.size
            if total - pos < length:
                self.truncated += 1
                break
            try:
                rec = json.loads(blob[pos:pos + length].decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                self.truncated += 1
                break
            pos += length
            self._apply(rec)
            replayed += 1
        return replayed

    def _apply(self, rec):
        kind = rec.get("type")
        if kind == "init":
            return
        if kind == "grant":
            # epoch 只许单调向前：重放旧日志也不能把 epoch 拉回去。
            self.epoch = max(self.epoch, int(rec.get("epoch", 0)))
            self.holder = rec["holder"]
            self.expiry = rec["expiry"]
            self.grants += 1
            self._journal.append(rec)
        elif kind == "write":
            self.writes.append(rec)
            self.accepted_writes += 1
            self._journal.append(rec)
