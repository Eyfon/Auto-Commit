# AI 安装指南

这份文档供能访问终端和 GitHub 的 AI 助手执行。上游地址为 `https://github.com/Eyfon/Auto-Commit`。用户要求“安装这个项目”时按本指南操作；如果用户只是在阅读、审查或开发代码，不执行部署。

## 目标和默认选项

用户没有指定时：使用当前登录 GitHub 账号的个人空间，新建私密独立仓库 `daily-activity`，北京时间每天 09:17 触发，当天随机提交 1～10 次。安装器验证成功后启用，安装时不执行每日提交。

采用模板生成独立仓库。不要把 `Eyfon`、示例邮箱或当前工作流触发者硬编码成安装者身份；不要修改上游开源仓库的定时开关，也不要接管用户无关的已有仓库。

## 1. 检查环境

检查 `git --version`、`python --version`（至少 3.10）、`gh --version` 和 `gh auth status --hostname github.com`。macOS / Linux 可能用 `python3`，Windows 可能用 `py -3`。

缺少工具时，按用户系统和已授权范围安装 Git、Python 或官方 GitHub CLI。不要假装已经安装成功。未登录时执行 `gh auth login --hostname github.com`，由用户完成浏览器或设备授权流程。不要读取本机凭据文件，不要让用户在聊天里粘贴密码或 token，不输出任何 token。

支持 GitHub.com。CLI 登录账号需要有创建个人仓库、管理 Actions 和写入工作流的权限。若 GitHub 明确提示缺少 workflow scope，可执行 `gh auth refresh --hostname github.com -s workflow`，由用户完成新增授权。组织策略无法绕过。

## 2. 获取代码与预览

克隆到新的工作目录，避免覆盖现有文件。若当前已经是从本上游克隆的源码，可复用并确认代码版本：

```sh
git clone https://github.com/Eyfon/Auto-Commit.git
cd Auto-Commit
python scripts/install.py --repository daily-activity --dry-run
```

预览会读取当前登录账号和目标仓库状态，展示目标地址、可见性及提交身份，不更改 GitHub。用户明确指定的仓库名或公开设置优先于默认值。

如果目标名已存在且不是此次安装创建的副本，保留它，选择可用的新名称或询问用户；不要清空、覆盖或删除已有仓库。只有确认继续此前安装时才使用 `--resume`。

## 3. 安装

```sh
python scripts/install.py --repository daily-activity
```

如果用户要求公开自己的副本，加 `--public`。安装器会通过 GitHub 模板 API 创建独立仓库，设置 `COMMIT_NAME`、`COMMIT_EMAIL`，运行 `verify_only=true` 的 Actions 检查并等待结果，最后才设 `AUTO_COMMIT_ENABLED=true`。

不需要为同仓库运行创建 PAT、Actions secret 或用户机器的定时任务。后续每天由 GitHub Actions 执行，电脑可以关机。

用户要求改时间时，完成安装后克隆**用户自己的新副本**，修改 cron 并推送到默认分支。cron 按 UTC 解释；默认记录日期使用 Asia/Shanghai。以用户明确指定的时区为准换算，并说明日期计算方式仍为北京时间。不要仅修改本地上游克隆后宣称远程已生效。

## 4. 验证与恢复

安装器输出 `Installed and enabled` 后，再读回配置以确认开关：

```sh
gh variable get AUTO_COMMIT_ENABLED --repo YOUR_USERNAME/daily-activity
gh variable list --repo YOUR_USERNAME/daily-activity
gh run list --repo YOUR_USERNAME/daily-activity --workflow daily-commit.yml --limit 3
```

需要看到变量为 `true`，这次只读检查对应的运行结果为 `success`，且 `commit` 作业实际成功执行，不能把 `skipped` 当通过。安装器会检查这些条件；日志中的仓库地址和提交身份也应匹配使用者账号。只读检查不测试真实写入权限，不要声称已经完成一次实际提交。

新仓库创建后如果网络、授权或 Actions 检查中断，仓库会保留，自动提交开关保持关闭。排查报错后运行：

```sh
python scripts/install.py --repository daily-activity --resume
```

若检查仍在队列中，可以查看 Actions，等待或稍后重试，不要为了检查而额外执行真实批次。查看错误时不要暴露 token。常见错误处理见 `docs/CONFIGURATION.md`。

## 5. 向用户交付

报告：新仓库地址、公开/私密状态、固定触发时间及其时区、每天随机 1～10 次、检查链接和检查结论。说明暂停方法，必要时指出 GitHub 调度可能延迟。如果授权或检查没有完成，明确说明停在哪一步以及下一步，不要声称安装成功。
