# macOS 实机构建与联调 Runbook

这个 runbook 只解决一件事：在 macOS 主机上构建 `.app` / `.dmg` / 便携 zip，并完成启动、更新、回滚、局域网访问联调。

## 环境前提

建议使用当前项目支持的 macOS 主机，具备以下工具：

- Python 3.11+
- `pip`
- `PyInstaller`
- Xcode Command Line Tools
- `hdiutil`

确认命令：

```bash
python3 --version
python3 -m PyInstaller --version
xcode-select -p
hdiutil help >/dev/null
```

## 一次完整构建

### 1. 安装构建依赖

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install pyinstaller
```

### 2. 构建 payload

```bash
python3 packaging/macos/payload/build_payload.py
```

检查：

- `packaging/macos/payload/app-base.zip`
- `packaging/macos/payload/manifest.json`

### 3. 构建静态更新源

```bash
python3 packaging/macos/publish_release.py --update-base-url https://your-domain.example/infinite-canvas/macos
```

检查目录：

```text
dist/macos-release/
  VERSION
  manifest.json
  app-base.zip
  <version>/
    VERSION
    manifest.json
    app-base.zip
```

### 4. 构建 `.app`

```bash
python3 packaging/macos/build_app.py
```

检查：

- `dist/macos/Infinite Canvas.app`
- `dist/macos/Infinite Canvas.app/Contents/MacOS/Infinite Canvas`
- `dist/macos/Infinite Canvas.app/Contents/MacOS/Infinite Canvas Service`
- `dist/macos/Infinite Canvas.app/Contents/MacOS/Infinite Canvas Updater`

### 5. 构建 `.dmg`

```bash
python3 packaging/macos/build_dmg.py
```

检查：

- `dist/macos/Infinite Canvas-<version>.dmg`

### 6. 构建便携 zip

```bash
python3 packaging/macos/build_portable.py
```

检查：

- `dist/macos/Infinite-Canvas-macOS-Portable.zip`
- zip 内包含 `Infinite Canvas.app/Contents/MacOS/Infinite Canvas`
- zip 内包含 `Infinite Canvas.app/Contents/Resources/bootstrap/app-base.zip`

## 启动联调

双击打开：

```text
dist/macos/Infinite Canvas.app
```

验证点：

- 浏览器自动打开本地页面
- `~/Library/Application Support/InfiniteCanvas/runtime/<version>` 被创建
- `~/Library/Application Support/InfiniteCanvas/data` 被创建
- `~/Library/Application Support/InfiniteCanvas/data/launcher-state.json` 记录端口
- 页面可正常调用本地 API

## 更新联调

先发布 `dist/macos-release/` 到静态源。

验证点：

- `/api/launcher/check-update` 能发现新版本
- `/api/launcher/apply-update` 成功
- `~/Library/Application Support/InfiniteCanvas/backups/launcher/` 下新增备份
- `current.txt` 指向新版本

## 回滚联调

完成一次更新后，执行页面中的回滚操作。

验证点：

- 页面能列出 launcher 备份
- 选择备份后能成功调用 `/api/launcher/rollback`
- `current.txt` 切回旧版本
- 重启 `.app` 后回到旧版本

## 局域网访问联调

打包版服务监听 `0.0.0.0:<实际端口>`。默认优先尝试 `3000`，如果被占用会自动切到其他空闲端口。

验证本机端口：

```bash
lsof -nP -iTCP -sTCP:LISTEN | grep Python
```

从另一台同网段设备访问：

```text
http://<局域网 IP>:<实际端口>/
```

如果 macOS 弹出网络访问权限提示，需要允许。

## 签名与 notarization

本轮只实现本地 `.app` / `.dmg` 构建。正式分发前还需要：

- `codesign`
- `notarytool`
- `stapler`

这三步建议作为单独发布流程处理。
