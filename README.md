# Auto-Commit

[![Tests](https://github.com/Eyfon/Auto-Commit/actions/workflows/test.yml/badge.svg)](https://github.com/Eyfon/Auto-Commit/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

每天固定时间，向你自己的 GitHub 仓库提交随机 **1～10 次 commit**。运行在 GitHub Actions 上，无需服务器、无需保持电脑开机、无需 Python 第三方依赖。

默认北京时间 **09:17** 触发，一次运行连续完成当天的提交。同一天重复运行会跳过已完成的批次，中途失败可以继续剩余次数。每次都实际更新 `activity/daily.json`，不伪造提交日期。

**[交给 AI 安装](#交给-ai-安装) · [自己安装](#自己安装) · [网页安装](#通过-github-网页安装) · [配置与排错](docs/CONFIGURATION.md) · [English](README.en.md)**

## 交给 AI 安装

把下面这段话发给**能执行命令、访问 GitHub 的 AI 编程助手**即可：

```text
请帮我安装 https://github.com/Eyfon/Auto-Commit 。
先阅读仓库 README.md 和 docs/AI-INSTALL.md，按指南完成安装和验证。
使用我当前登录的 GitHub 账号，默认新建名为 daily-activity 的私密独立仓库，
每天北京时间 09:17 自动提交，次数随机 1～10 次。
```

AI 会检查 Git、Python 和 GitHub CLI，使用你本机已有的 GitHub 登录状态，运行安装脚本，并报告仓库地址和检查结果。首次使用时可能需要你在浏览器完成 GitHub 登录；普通聊天机器人没有执行环境时无法直接安装。不要把密码或 token 发给 AI。

想用其他仓库名、公开仓库或其他时间，直接在这段话后补充。仅发送仓库地址时，AI 可以从 README 找到安装入口，但能否自动执行取决于该助手的能力和权限。

## 自己安装

需要 **Python 3.10+、Git、[GitHub CLI](https://cli.github.com/)**。以下命令适用于 macOS / Linux / Windows PowerShell；某些系统需将 `python` 替换为 `python3` 或 `py -3`。

```sh
gh auth login --hostname github.com
git clone https://github.com/Eyfon/Auto-Commit.git
cd Auto-Commit
python scripts/install.py --repository daily-activity
```

已经登录时可以跳过第一条，用 `gh auth status --hostname github.com` 检查。登录授权需允许创建仓库、写入工作流和管理 Actions 变量；若 GitHub 提示缺少 workflow scope，按提示执行 `gh auth refresh --hostname github.com -s workflow`。

安装脚本会：

1. 根据当前 GitHub 登录账号，在该账号下创建 `daily-activity` 私密仓库。
2. 从此模板生成独立副本，自动设置该账号的提交名和 GitHub 隐私邮箱。
3. 运行一次**只读检查**，等待 GitHub Actions 检查成功。
4. 启用每日自动提交；第一次批次在下一个定时触发点执行。

安装时不创建每日活动提交。检查验证读取和配置，不保证未来的写入不受分支保护、组织策略或额度变化影响。GitHub 可能延迟定时任务，不保证精确到点。

可选命令：

```sh
# 先预览安装计划，不更改 GitHub
python scripts/install.py --repository daily-activity --dry-run

# 明确创建公开副本
python scripts/install.py --repository daily-activity --public

# 上一次安装已创建仓库，但配置或检查中断：修复问题后继续
python scripts/install.py --repository daily-activity --resume
```

`--resume` 只接受从本模板生成的独立仓库，保留已有内容和可见性。安装器不会接管无关仓库，也不会删除仓库；检查失败时自动提交保持关闭。

## 通过 GitHub 网页安装

1. 点击 **[Use this template → Create a new repository](https://github.com/new?template_name=Auto-Commit&template_owner=Eyfon)**，创建到自己的个人账号，选择公开或私密。
2. 进入新仓库的 **Actions**，若出现提示，先启用工作流。
3. 打开 **Actions → Daily commit → Run workflow**，保持 `verify_only` 勾选，等待检查通过。
4. 打开 **Settings → Secrets and variables → Actions → Variables → New repository variable**，添加 `AUTO_COMMIT_ENABLED`，值填 `true`。

个人仓库会自动读取仓库所有者的用户名和账号 ID，生成对应的 GitHub 隐私邮箱。需要指定其他身份时，同时设置 `COMMIT_NAME` 和 `COMMIT_EMAIL`。组织仓库必须设置这两个变量，邮箱应属于你希望计入贡献的个人账号。

请使用 **Use this template** 创建独立仓库。GitHub 对 fork 仓库的提交有额外贡献统计限制，直接使用模板更合适。开源源仓库默认未启用自动提交，你需要在自己的副本启用。

## 日常使用

| 操作 | 方法 |
| --- | --- |
| 查看执行记录 | 自己仓库的 **Actions → Daily commit** |
| 只读检查 | **Run workflow**，保持 `verify_only` 勾选 |
| 立即执行或补齐当天批次 | 启用后手动运行，取消勾选 `verify_only` |
| 暂停 | 将 `AUTO_COMMIT_ENABLED` 改为 `false`，或在 Actions 禁用工作流 |
| 恢复 | 变量改回 `true`；若禁用了工作流，还需重新启用 |
| 更改执行时间 | 编辑自己副本的 `.github/workflows/daily-commit.yml`，提交到默认分支 |
| 向另一个仓库提交 | 见[跨仓库配置](docs/CONFIGURATION.md#向另一个仓库提交) |

当前 cron 为 `17 1 * * *`（UTC），对应北京时间 09:17。例如北京时间 22:35 对应 `35 14 * * *`。每日进度始终按北京时间计算。

## 贡献热力图与隐私

提交邮箱需要关联到你的 GitHub 账号，提交应位于目标仓库的默认分支等符合 GitHub 贡献规则的位置。向非默认分支写入不保证计入热力图。显示更新通常会有延迟，具体以 [GitHub 贡献规则](https://docs.github.com/en/account-and-profile/how-tos/contribution-settings/troubleshooting-missing-contributions)为准。

私密仓库用户可以在**个人主页 → 贡献热力图右上角 → Contribution settings → Private contributions** 开启匿名私密贡献展示。公开热力图不会因此公开私密仓库名称或提交内容；有仓库访问权限的人仍可看到提交详情和时间。

GitHub Actions 的权限、额度和调度限制见[配置文档](docs/CONFIGURATION.md)。此项目是自动化示例，贡献方块代表活动数量，不代表实际项目成果。

## 开发与升级

```sh
python -m unittest discover -s tests -v
```

测试不需要网络或 GitHub token。CI 在 Ubuntu / Windows 和 Python 3.10 / 3.12 上运行。架构、进度文件说明及手动升级步骤见[开发文档](CONTRIBUTING.md)。模板副本不会自动同步上游更新。

## 许可证

[MIT License](LICENSE) © 2026 Eyfon。
