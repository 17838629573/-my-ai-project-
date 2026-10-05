# FILL driver   缺 2 槽位   （模型只填 pick，勿写散文）

## 否决方案 (neglected)
已填: 无
  [IMPROVE:IMPROVE_driver.md:L4] 之前对树、马车也生成骨架/序列帧 —— 因为代码没有"先判族、再选驱动器"这一层，
  [IMPROVE:IMPROVE_driver.md:L25] 解法：只扫 `# BEGIN EXAMPLES` 之前的源码。
  [driver.py:L348] 14 证伪：物体缺族时队列建立失败，必须明说而非静默跳过
  pick: NEW: 否决「不判族一律按 biped/chain 处理」——树/马车被误生成骨架

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_driver.md:L23] 3. **自检自指误报（第 5 次遇到同类）**
  pick: IMPROVE_driver.md:23
