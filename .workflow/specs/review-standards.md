---
title: "Review Standards"
readMode: required
priority: medium
category: review
keywords:
  - review
  - checklist
  - gate
  - approval
  - standard
---

# Review Standards

## Entries

<spec-entry category="review" keywords="upstream-sync branch-flow main docker pkg default-branch" date="2026-07-14" sid="S-20260714-l745" title="纯上游 main 与 docker/pkg 串行继承规则" description="main 纯上游，docker 最小容器适配，pkg 桌面与增强实现，单向串行继承" source="user:2026-07-14" supersedes="S-20260714-8uvb">

### 纯上游 main 与 docker/pkg 串行继承规则

本 fork 的分支职责固定为：main 必须与 hero8152/Infinite-Canvas 的 upstream/main 保持 commit 和 tree 一致，不承载任何 Docker、桌面打包、AI 协作资产或其他 fork-only 改动；docker 只能从本 fork 的 main 向下合并，承载最小 Docker、容器运行和容器所需的即梦 runtime 适配；pkg 只能从本 fork 的 docker 向下合并，承载 Windows/macOS 桌面打包、launcher、更新发布、AI 协作资产以及 pkg 自己的 Docker/runtime 增强。标准同步方向唯一为 upstream/main → main → docker → pkg。禁止 docker 或 pkg 直接合并外部上游，禁止 main 直接合并到 pkg，禁止 pkg 改动反向回流 docker，禁止 docker 改动反向回流 main。pkg 可以覆盖或增强从 docker 继承的 Dockerfile、app_runtime 和发布实现，这些增强默认只属于 pkg。GitHub 默认分支设为 pkg，以保证 fork README 和 release/workflow_dispatch 工作流存在于默认分支。每次同步前保护脏工作区并优先使用独立 worktree；main 同步后验证与 upstream 完全一致，docker 阶段执行 Docker 实际构建与容器启动验证，pkg 阶段执行全量测试及对应平台安装包构建。

</spec-entry>
