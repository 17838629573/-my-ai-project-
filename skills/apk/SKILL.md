---
name: apk
description: 步骤7 打 Android APK。交付 APP 时读，其他时候不读。
---

# 打包 APK

1. 构建工具链在不在（gradle / SDK）？缺 → 读 `skills/halt/SKILL.md`。
2. 先出 Debug 包：构建 → 安装 → 启动验证。
3. 启动失败 → 看 logcat 报错，按 `skills/test/SKILL.md` 三层扫描定位，读 `skills/fix/SKILL.md` 修。
4. Debug 包验证通过后，再出 Release 包。

过门：APK 安装后能启动主界面 + 验证声明（`skills/verify/SKILL.md`）。
