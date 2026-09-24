"""把 sample/lease.json 跑一遍，打印验收面（两个子系统）。"""
import json
import os
import sys

from leaselog import LeaseLog
from writer import Writer


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join("sample", "lease.json")
    with open(path, encoding="utf-8") as handle:
        spec = json.load(handle)
    log = LeaseLog()
    writer = Writer(log)
    rows = []
    accepted = 0
    replayed = 0
    for event in spec["events"]:
        if event["op"] == "grant":
            epoch = log.grant(event["holder"], spec["ttl"], event["at"])
            rows.append((event["at"], "grant", epoch))
        elif event["op"] == "commit":
            ok = writer.commit(event["holder"], event["value"], event["at"], event.get("token"))
            if ok:
                accepted += 1
            rows.append((event["at"], "commit", ok))
        elif event["op"] == "crash":
            blob = log.dump() + b'{"op":"write","holder":"c1","va'  # 模拟崩溃撕裂的半条记录
            log = LeaseLog()
            replayed = log.load(blob)
            writer = Writer(log)
            rows.append((event["at"], "crash-replay", replayed))
    print("事件结果 =", rows)
    print("最终 epoch =", log.epoch)
    print("接受的写数 =", accepted)
    print("被拒的写数 =", log.rejected)
    print("重放条数 =", replayed)
    print("残尾忽略 =", log.truncated)
    print("重放后 epoch 不回退 =", log.epoch >= spec["expect_min_epoch"])
    print("租期 =", spec["ttl"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
