# Windows Packaging

本目录承载 Windows 分发层，目标是尽量不改现有业务代码：

- `launcher/`：启动器与模式判定逻辑
- `installer/`：Inno Setup 安装与卸载脚本
- `payload/`：运行时资源清单与构建辅助文件
- `updater/`：更新器实现
- `build_launcher.py`：使用 `PyInstaller` 构建 `launcher.exe` / `updater.exe`
- `publish_release.py`：生成静态更新源目录
- `WINDOWS_RUNBOOK.md`：Windows 实机构建、安装、更新、回滚、卸载联调手册

核心约束：

- 安装目录可写时，走 `in_place` 模式
- 安装目录不可写时，走 `runtime` 模式
- 用户数据、日志、备份统一落到 `storage_root`
- 打包版默认优先使用 `3000`，若端口被占用则自动避让并持久化最后一次成功端口
- 卸载时必须显式选择“保留数据”或“不保留数据”

## 当前构建步骤

1. 生成 payload：

```bash
python3 packaging/windows/payload/build_payload.py
```

2. 生成静态更新源目录：

```bash
python3 packaging/windows/publish_release.py --update-base-url https://example.com/infinite-canvas/windows
```

默认输出到 `dist/windows-release/`，结构如下：

```text
dist/windows-release/
  VERSION
  manifest.json
  app-base.zip
  2026.05.24.1/
    VERSION
    manifest.json
    app-base.zip
```

根目录给已安装客户端检查最新版，版本子目录用于归档和审计。

3. 构建启动器和更新器：

```bash
python3 packaging/windows/build_launcher.py
```

4. 使用 Inno Setup 编译：

- 脚本：`packaging/windows/installer/infinite-canvas.iss`
- 需要把生成的 `launcher.exe`、`updater.exe` 与 payload 文件一起纳入安装产物

## 当前状态

已完成：

- 双模式判定逻辑
- `storage_root` 目录设计
- payload 构建器
- 静态更新源目录构建器
- 安装器自定义 `storage_root` 页面
- 卸载时强制二选一的数据保留窗口
- 主程序最小兼容层：支持 `INFINITE_CANVAS_DATA_ROOT`
- launcher 版更新与回滚 API
- launcher 更新前自动备份，支持 `in_place` / `runtime` 两种模式回滚

待完成：

- 在 Windows 主机上实际构建 `launcher.exe` / `updater.exe`
- 用 Inno Setup 实机编译并验证安装/卸载流程
- `launcher.exe` / `updater.exe` 自身更新策略
- 启动器的 Windows UI 细节与日志展示
