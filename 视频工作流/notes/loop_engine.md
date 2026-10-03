# loop_engine 改动史

## 引擎级 initialized vs ctx 级状态（架构级，实测）

`System.initialized` 是**引擎级**标记，但 init 的结果写在 **ctx** 上。
渲染多镜头时每镜新建 ctx → 第 2 镜起 init 被跳过 → `ctx.skeleton = None`
→ `update_animation` 静默 return。

实测证据（composite 单帧耗时）：

| 镜 | 耗时 | 判读 |
|---|---|---|
| 01_gate | 15.678 ms | 骨架画出来了 |
| 05_river | 0.142 ms | 骨架没画 |

差 110 倍。镜 5/6/8（走路）全是空镜，但日志显示 skeleton 系统"已启用"。

修法：`_ensure_init` 绑定 ctx 身份

```python
key = id(ctx)
if self._init_ctx != key and self._init_fn:
    self._init_fn(ctx)
    self._init_ctx = key
```

`reset_stats` 一并清 `_init_ctx`。

修复后 8 镜前景像素全部 >0（此前 3 个空镜）。
