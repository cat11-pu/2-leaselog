# leaselog

纯 Python 标准库的 leaselog（无第三方依赖）。

## 语义

- `grant(holder, ttl, now)`：每次授予让 `epoch` 单调加一（含过期后重授），返回新 epoch。
- `renew` 类操作不应触碰 epoch；`check(holder, token, now)` 做 fencing：
  租约过期、持有者不符、或 `token < epoch` 一律拒绝并计入 `rejected`；
  `token=None` 的老调用方不受影响。
- `dump()` / `load(blob)`：JSON Lines 落盘与重放（meta + grant + write 记录），
  恢复时 epoch 取最大值不回退；尾部无换行终止的半条记录被忽略并计入 `truncated`。

## 测试

    python3 -m unittest discover -s tests -v

## 场景自检

    python3 check_sample.py
