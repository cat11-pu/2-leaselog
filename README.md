# leaselog

纯 Python 标准库的 leaselog（无第三方依赖）。

## 语义

- `grant(holder, ttl, now)`：epoch 单调加一，过期后重新授予也是新 epoch；`renew` 只续租期，不动 epoch。
- `check(holder, token, now)`：fencing 校验——token 小于当前 epoch、持有者不符、租约过期，一律拒绝并计入 `rejected`；`token=None` 兼容老调用方。
- `dump()` / `load(blob)`：授予与写记录以 JSONL 落盘（末尾附 checkpoint），崩溃重放后 epoch 不回退；尾部半条记录忽略并计入 `truncated`。
- `writer.commit(holder, value, now, token=None)`：接 fencing 校验，不带 token 的老写法继续可用。

## 测试

    python3 -m unittest discover -s tests -v

## 场景自检

    python3 check_sample.py
