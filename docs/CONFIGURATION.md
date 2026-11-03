# 配置与排错

## Actions 变量

位置：**程序仓库 → Settings → Secrets and variables → Actions → Variables**。以下都属于 repository variables，不是 secrets。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AUTO_COMMIT_ENABLED` | 未设置，关闭 | 精确填 `true` 才执行每日提交；只读检查可以在关闭时运行 |
| `COMMIT_NAME` | 个人仓库所有者用户名 | 安装器设为当前登录用户名 |
| `COMMIT_EMAIL` | 个人仓库所有者的 GitHub 隐私邮箱 | 安装器设为 `账号ID+用户名@users.noreply.github.com` |
| `TARGET_REPOSITORY` | 当前程序仓库 | 可填 `owner/repository`，跨仓库需要下述 secret |
| `TARGET_BRANCH` | 目标仓库默认分支 | 必须已经存在；非默认分支上的提交可能不计入贡献 |
| `COMMIT_FILE` | `activity/daily.json` | 程序管理的进度文件，新安装选尚不存在的路径 |

`COMMIT_NAME` 和 `COMMIT_EMAIL` 必须一起设置或一起留空。组织仓库不能从组织账号推断个人提交者，必须设置两项。隐私邮箱可在 [GitHub Settings → Emails](https://github.com/settings/emails) 核对，也可使用关联到账号的真实邮箱；真实邮箱会出现在 commit 元数据中。

## 向另一个仓库提交

默认向自己的安装副本提交，无需额外 token。如果你要把程序和活动记录分开存放：

1. 目标仓库和目标分支必须已有至少一次初始提交，例如创建 README。
2. 在程序仓库添加变量 `TARGET_REPOSITORY=owner/target-repo`。需要时设 `TARGET_BRANCH`。
3. 在 GitHub 创建仅授权目标仓库的 fine-grained PAT，授予 **Contents: Read and write**，并确保目标所有者/组织批准所需授权。
4. 在程序仓库 **Settings → Secrets and variables → Actions → Secrets** 添加 `TARGET_TOKEN`。不要放入 Variables 或代码。
5. 手动运行 `Daily commit`，保持 `verify_only` 勾选，检查目标地址和作者信息。通过后由定时任务执行，或按需手动执行一次批次。

内置 `GITHUB_TOKEN` 只能操作其所属仓库。组织 token 策略、分支保护和 rulesets 仍然生效；自动化需要能直接更新所选分支，要求 PR 的分支通常不适合本程序。

## 时间与随机次数

编辑自己副本 `.github/workflows/daily-commit.yml` 中：

```yaml
schedule:
  - cron: '17 1 * * *'  # UTC 01:17，北京时间 09:17
```

提交到默认分支才生效。GitHub cron 使用 UTC，不自动处理用户所在地夏令时。每日进度由程序按固定 UTC+8（Asia/Shanghai）计算，与电脑时区无关。

每天首次成功写入时保存随机目标次数，范围固定 1～10（两端均包含）。当天剩余提交立即连续完成，不随机分散到多个时刻。重复运行读取同一目标次数；当天已完成就跳过，中断则恢复剩余次数。不回填错过的日期，不改写历史提交时间。

## 进度文件

```json
{
  "generator": "github-daily-commit/v1",
  "date": "2026-11-04",
  "timezone": "Asia/Shanghai",
  "target_commits": 3,
  "completed_commits": 3
}
```

每条 commit 更新一次进度，历史保存在 Git 中。程序不会覆盖非本程序生成的文件，不允许写入 `.git` 或 `.github`。保留进度文件；删除文件或换路径会让当天被认为尚未运行，可能产生额外提交。旧版本同一天的记录会视为完成，下一天开始新模式。

## 常见问题

### 没有按时执行

确认 `AUTO_COMMIT_ENABLED=true`、工作流已启用且 YAML 位于默认分支。GitHub 定时运行可能延迟或因负载被丢弃；这是托管调度限制，无法承诺每天准点。公开仓库长期无活动（通常 60 天）后，定时工作流可能被停用，需要在 Actions 页面重新启用。

### 安装提示权限不足或 HTTP 403

确认 `gh auth status --hostname github.com` 的账号正确，拥有创建个人仓库、工作流和 Actions 变量权限。缺少 workflow scope 时运行 `gh auth refresh --hostname github.com -s workflow` 并完成浏览器授权。组织或企业禁用了 Actions、禁止指定 action 或禁止写权限时，需要仓库管理员处理。

工作流声明 `permissions: contents: write`。同仓库无需手动创建 PAT。仓库/组织策略、分支保护、rulesets 和额度仍可阻止写入。只读检查不证明真实写入权限。

### HTTP 404

检查仓库名、目标分支是否存在、token 是否有权访问私密仓库。刚创建的模板副本需要一点时间注册工作流，安装器会等待；如果超时，可查看 Actions 后加 `--resume` 重试。GitHub 对无权访问的私密仓库也可能返回 404。

### 安装器中途退出

保留已创建仓库，修复错误后执行 `python scripts/install.py --repository 你的仓库名 --resume`。不需要删除重建。`--resume` 会先关闭自动提交，再验证配置，通过才重新开启。

### 手动运行只有 skipped

关闭自动提交时，仅勾选 `verify_only` 的手动检查会执行。要执行真实批次，先启用变量，再取消勾选 `verify_only`。当天已完成时日志会显示 `Completed ... no more commits needed`。

### 热力图没变化

核对提交详情里的作者邮箱是否关联到你的账号，目标是否为独立仓库默认分支，以及 GitHub 统计是否仍在更新。私密贡献需在个人主页的 Contribution settings 开启 Private contributions。不要通过反复删除进度文件来排查。

### 费用与停用

公开仓库使用标准 GitHub-hosted runner 通常可免费运行；私密仓库消耗账号的 Actions 分钟额度，用量和计费以 GitHub 当前套餐为准。此项目默认每天仅启动一次。

暂停时将 `AUTO_COMMIT_ENABLED` 改为 `false` 或禁用工作流。关闭电脑不会暂停 GitHub 上的任务。彻底移除可删除自己副本的 `daily-commit.yml`；删除整个仓库会丢失其中内容，请自行确认。
