# 开发说明

Python 3.10+，仅使用标准库。不需要安装 requirements。运行：

```sh
python -m unittest discover -s tests -v
git diff --check
```

## 结构

| 文件 | 用途 |
| --- | --- |
| `scripts/daily_commit.py` | 使用 GitHub Contents API 读取进度并提交每日批次 |
| `scripts/install.py` | 通过 GitHub CLI 创建模板副本、配置变量、检查并启用 |
| `.github/workflows/daily-commit.yml` | 每日定时与手动检查入口 |
| `.github/workflows/test.yml` | Windows/Ubuntu、Python 3.10/3.12 的离线测试 |
| `docs/AI-INSTALL.md` | AI 助手可执行的安装指南 |
| `docs/CONFIGURATION.md` | 配置、权限、时间、隐私与排错 |

核心脚本以远程文件 SHA 作为更新前提，冲突时重新读取已保存的目标次数及进度，最多允许三次连续冲突；不覆盖其他文件。随机次数只在当天尚无记录时生成。只读检查不会写入或提前抽取次数。

安装器通过参数列表调用 `gh`，API JSON 使用 stdin，不拼 shell 命令，不读取或输出 token。创建仓库、设置变量和工作流需要用户已授权的 GitHub 登录。安装失败后保留仓库，保持自动提交关闭，支持 `--resume`。

离线测试覆盖每日 1～10 次、日期切换、重试、并发冲突、作者身份、只读模式、原文件保护、安装成功/失败/恢复等。真实 GitHub 网络、账号权限和调度不由离线测试模拟结果保证；部署后应另做只读 Actions 检查。

## 本地运行每日脚本

通过环境变量注入 `GITHUB_TOKEN`，不要将值写入仓库。至少配置 `SOURCE_REPOSITORY=your-name/your-copy`（或 `TARGET_REPOSITORY` 加明确的 `COMMIT_NAME` 和 `COMMIT_EMAIL`）。然后：

```sh
python scripts/daily_commit.py --check
```

`--dry-run` 同样只读。去掉检查选项会真正执行或恢复当天的每日批次。Actions 的启用变量只在工作流入口检查，本地执行写入命令代表直接操作目标仓库。

## 升级安装副本

GitHub 模板副本不会自动跟随上游更新。先比较上游变更，再把需要的新 `scripts/` 和工作流文件应用到自己的副本，保留自定义 cron、作者变量、目标仓库和 `activity/daily.json`。运行测试，推送到自己副本的默认分支，再执行 `verify_only=true` 检查。不要 force-push 覆盖已有活动历史。

欢迎通过 issue 或 PR 提交可复现问题和改进，PR 请说明改动及验证结果。
