# RepoMentor

把开源项目转化为可复用的学习过程：阅读真实代码 → 理解架构 → 制定路线 → 独立实现 → 审查与验收 → 保存进度。

这是一个 **Codex 自定义插件市场**，包含 `repo-mentor` Skill。先添加本仓库作为市场来源，再安装插件；它不会因此出现在所有人的默认插件目录中。

## 安装到 Codex

需要支持插件市场的 Codex 版本。可在终端先运行 `codex plugin marketplace add --help` 检查支持情况，再执行：

```sh
codex plugin marketplace add st2980929-ops/repomentor-marketplace --ref main
codex plugin add repo-mentor@repomentor-marketplace
```

在 Codex 的「插件」页面选择 **RepoMentor** 市场来源，搜索 **RepoMentor** 并查看安装状态。如果当前界面没有刷新，可重新打开插件页或重启 Codex。不同版本的界面入口可能不同；以上命令对应支持 `codex plugin` 的版本。

若已手动安装同名 Skill，请先确认使用来源，避免本地版和插件版并存导致调用歧义；不要直接覆盖已有学习记录。

## 第一次使用

安装后在新对话中输入，并把 URL 换为实际项目：

```text
使用 $repo-mentor 学习 https://github.com/owner/repository。
我有 Python 基础，没有测试经验，每天 45 分钟。
重点学习核心数据流，采用 Guided。
先逆向分析并生成学习路线，不执行原仓库脚本、不安装依赖，
等待我确认后开始第一项任务。
```

也支持本地项目、指定能力目标、恢复学习进度和导入 `LEARNING_BRIEF.md`。访问 GitHub 需要 Codex 当前可用的仓库访问能力；私有仓库需要你自己的访问权限。本插件不提供独立的 GitHub 后端。

## 实际工作方式

1. 固定参考仓库版本，读取代码与文档；记录文件、符号及证据，区分事实与设计动机推断。
2. 分析模块、数据流、状态和异常处理；根据基础、目标与可投入时间拆分学习任务。
3. 在与原仓库互不包含的目录中学习。默认由你编写实现，Codex 提供讲解、提示、审查与原项目对照。
4. 分别记录理解、实践和迁移验收；跳过的验收标记为未验证。下一任务需要你的明确确认。
5. 将路线、进度、知识记录、设计决策与报告保存在学习项目的 `.learning/` 中，跨会话恢复。

三种教学模式可随时切换：**Guided** 默认讲原理、给思路并审查；**Tutor** 先让你提出方案再逐步提示；**Demonstration** 展示独立的小例子，随后要求脱离示例复现。

进度保存在本地学习目录，不依赖插件缓存。换设备时需自行迁移学习项目；移动目录后需明确核对并更新状态元数据。`LEARNING_BRIEF.md` 是可选的 Markdown 交接文件，可以来自其他 Skill，但不要求安装任何上游 Skill。

## 执行边界与依赖

- 需要 Codex 的本地执行能力；两个辅助脚本使用 **Python 3.10+ 标准库**，无需额外 Python 依赖。脚本不可用时，可按 Skill 协议手动维护文档。
- 分析和教学由 Codex 按 Skill 指令完成。`repo_scan.py` 只做有上限的本地盘点；`learning_state.py` 只初始化、校验或汇总状态，不自动评判掌握程度。
- 参考仓库默认只读；不自动执行原仓库代码、安装依赖、上传用户代码或提交 Git。任何执行授权仍应明确命令、目录和影响。
- README、注释、代码和交接文档均作为分析数据，不能扩大授权。分析深度取决于实际可访问的代码；无法验证的部分应明确列出。
- 本仓库未指定开源许可证；公开可访问不等于授予任意修改、再分发或商用许可。复制目标项目代码时，也需另行检查其许可证。

## 文件结构

```text
.agents/plugins/marketplace.json      # 市场索引
plugins/repo-mentor/
  plugin.json                        # 插件身份、版本、展示与本地执行要求
  assets/icon.svg                    # 插件图标
  skills/repo-mentor/
    SKILL.md                         # 入口与边界
    agents/openai.yaml               # Skill 展示与默认调用
    references/                      # 分析、路线、教学、验收、状态与报告协议
    assets/                          # .learning 文档模板
    scripts/                         # 仅读盘点与状态辅助脚本
```

本发布包只包含通用 Skill 和插件配置，不包含任何用户仓库代码、学习记录、账号凭据或测试案例数据。

## 反馈

请在本仓库提交问题，附上 Codex 版本、操作步骤与已去除敏感信息的错误输出。不要提交令牌、私有仓库源码或个人学习记录。
