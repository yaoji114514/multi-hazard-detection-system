---
name: 现场安全签派台
description: 以现场影像为核心的 PPE 风险校验与闭环处置工作台
colors:
  daylight-paper: "#EDF0F2"
  proof-white: "#F8F9F9"
  paper-low: "#DFE3E6"
  graphite: "#171B20"
  graphite-raised: "#262C32"
  ink: "#171B20"
  text-muted: "#5E6871"
  rule: "#AEB5BB"
  rule-strong: "#727C85"
  action-cobalt: "#075BBE"
  action-cobalt-deep: "#064B9D"
  risk-red: "#B72A22"
  risk-red-soft: "#F5E8E6"
  risk-yellow: "#925800"
  risk-yellow-soft: "#F5EDDC"
  safe-slate: "#3D5D73"
  safe-slate-soft: "#E6EDF1"
typography:
  display:
    fontFamily: "Microsoft YaHei UI, Microsoft YaHei, PingFang SC, Segoe UI, sans-serif"
    fontSize: "2rem"
    fontWeight: 800
    lineHeight: 1.15
    letterSpacing: "-0.035em"
  body:
    fontFamily: "Microsoft YaHei UI, Microsoft YaHei, PingFang SC, Segoe UI, sans-serif"
    fontSize: "0.88rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Microsoft YaHei UI, Microsoft YaHei, PingFang SC, Segoe UI, sans-serif"
    fontSize: "0.73rem"
    fontWeight: 700
    lineHeight: 1.4
rounded:
  control: "4px"
  surface: "4px"
  switch: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  control: "10px"
  md: "14px"
  lg: "18px"
  panel: "22px"
  page: "28px"
components:
  button-primary:
    backgroundColor: "{colors.action-cobalt}"
    textColor: "{colors.proof-white}"
    rounded: "{rounded.control}"
    padding: "10px 16px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.action-cobalt-deep}"
    textColor: "{colors.proof-white}"
    rounded: "{rounded.control}"
  input:
    backgroundColor: "{colors.proof-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "10px 12px"
    height: "44px"
  evidence-stage:
    backgroundColor: "{colors.graphite}"
    textColor: "{colors.proof-white}"
    rounded: "{rounded.surface}"
  dispatch-sheet:
    backgroundColor: "{colors.proof-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.surface}"
    padding: "22px"
---

# Design System: 现场安全签派台

## Overview

**Creative North Star: "安全影像校样台与现场签派条"**

界面像一张在日光环境中展开的工程影像校样台。真实现场照片是产品的主材料，石墨色证据舞台负责聚焦，右侧浅色签派条把项目、检查人、准备状态和下一步动作收拢到同一视线内。视觉冲击来自证据比例与操作结构，不来自装饰性工业拟物。

这是高密度 Operate 系统。熟悉的按钮、表单、顶部导航和状态语言保持直接；个性来自联系表、处置单、黑色校样框和克制的印刷式规则线。系统拒绝旧版深色侧栏后台，也拒绝通用白色卡片墙。

**Key Characteristics:**

- 现场影像始终比统计数字和技术配置更醒目。
- 日光银灰和石墨形成主世界，钴蓝只用于操作与当前选择。
- 红色、黄色只表达真实业务风险，并始终配合文字说明。
- 页面以大舞台、签派条、联系表和处置单组织，不堆叠同尺寸卡片。
- 动效只用于状态反馈、证据切换和抽屉过渡，并尊重减少动态效果设置。

## Colors

色彩像工程校样纸上的油墨：中性纸面承担大面积阅读，石墨固定证据边界，钴蓝标记可以执行的动作。

### Primary

- **Action Cobalt**：唯一普通交互强调色，用于主按钮、当前导航、焦点环和可操作链接。
- **Deep Cobalt**：钴蓝的悬停与按下状态，不用于装饰背景。

### Secondary

- **Risk Red**：未戴安全帽等立即处置风险，只出现在风险标记、证据框和错误恢复信息。
- **Risk Yellow**：限时整改风险，使用加深文字保证在浅黄纸面上的可读性。
- **Safe Slate**：已完成推理后的无违规或系统健康状态；摄像头尚未检测时不得使用。

### Neutral

- **Daylight Paper**：应用主背景，适合现场办公室与明亮屏幕环境。
- **Proof White**：签派条、处置单、抽屉和表单表面。
- **Graphite**：证据舞台、影像工具栏和主要结构边界。
- **Rule / Strong Rule**：校样线、字段分隔和主从区域边界。
- **Muted Ink**：说明、占位符和次级元数据，仍须达到正文对比度要求。

**The Semantic Signal Rule.** 钴蓝表示操作，红黄表示业务风险。监测状态、系统故障和普通选择不能借用红黄风险色。

**The Text Plus Color Rule.** 每个风险颜色旁必须有中文等级、当前事实或下一步动作。

## Typography

**Display Font:** Microsoft YaHei UI，回退至 Microsoft YaHei、PingFang SC、Segoe UI 和系统无衬线字体

**Body Font:** 与 Display 共用同一工作型字体栈

**Label Font:** 同一字体栈，以字重和尺寸区分，不使用等宽字体营造技术感

**Character:** 字体承担工程记录的清晰与可信。标题短、粗、紧凑；正文与表单保持常规字距；数字启用 tabular numerals 便于比较。

### Hierarchy

- **Display**（800，2rem，1.15）：页面任务标题，桌面保持单行或两行以内。
- **Headline**（800，1.28-1.55rem）：签派条、处置单和分析区块标题。
- **Title**（700，0.95rem）：证据名称、项目名称和关键状态。
- **Body**（400，0.88rem，1.55）：操作说明与恢复信息，连续说明控制在约 70ch 内。
- **Label**（700，0.68-0.78rem）：字段名、来源、时间和状态解释，不默认全大写或拉大字距。

**The Working Type Rule.** 标题靠字重和位置建立层级，不使用渐变文字、装饰斜体或巨大海报字号。

## Layout

桌面主内容最大宽度为 1680px，页面水平内边距为 28px。顶部 76px 单行栏同时容纳品牌、五项业务导航、检查上下文、模型状态和通知入口。核心页面采用不对称主从布局：证据舞台占剩余宽度，签派条固定约 360px；处置页使用联系表与右侧处置单，统计页使用积压账本与两种不同的数据布局。

第一视口必须完成一次任务闭环：用户能看到证据、上下文准备状态和主动作。签派条的准备状态、主按钮和说明锚定在影像下沿，不悬浮在中段。

在 920px 以下，顶部栏分为上下两行，主从区域改成单列。在 700px 以下，页面内边距降为 14px，五项导航继续保持同一行，图标隐藏，联系表卡片改成缩略图与文字的横向组合。390px 视口不得产生页面级横向滚动；需要横向选择的快捷视图在自己的容器内滚动。

**The Evidence First Rule.** 页面层级先呈现真实影像与当前动作，再呈现统计、技术参数和历史明细。

## Elevation & Depth

系统以色块、线条和影像裁切建立结构，默认保持平面。只有证据舞台、签派条、处置单和通知抽屉允许低幅环境阴影，用来表达真实的主从层级；普通指标、筛选和状态不用阴影包装。

### Shadow Vocabulary

- **Evidence Lift** (`0 12px 30px rgba(44, 55, 64, 0.16)`): 大证据舞台与背景分离。
- **Sheet Lift** (`0 10px 24px rgba(44, 55, 64, 0.11)`): 签派条和处置单的低幅纸面层级。
- **Drawer Lift** (`-16px 0 40px rgba(21, 27, 32, 0.20)`): 模态通知抽屉与被遮罩页面分离。

**The Flat By Default Rule.** 没有真实层级关系的内容使用留白或规则线，不使用阴影卡片。

## Shapes

主要表面和控件采用 4px 小圆角，接近裁切纸张与工程控件的方正语言。开关滑轨与圆形指示点是唯一长期使用的全圆角形状。证据图片由石墨舞台裁切，风险框保持直角；不得混入大圆角 SaaS 卡片。

边界以 1px 规则线为主，证据舞台和主工作区可使用更强的 2px 或 5px 顶部结构线。粗线只负责区域组织，不作为装饰性警戒条。

## Components

### Buttons

- **Shape:** 方正小圆角（4px），普通高度至少 44px。
- **Primary:** 钴蓝底、浅色文字；每个任务区域只保留一个主动作。
- **Hover / Focus:** 悬停进入深钴蓝；键盘焦点使用纸面间隔加钴蓝双环。
- **Disabled:** 保留完整动作标签，以降低饱和度表达不可用，旁边必须能看见缺失条件。

### Risk Marks

- **Style:** 浅色语义纸面、加深语义文字和 1px 边界；不是装饰胶囊。
- **State:** 红色为立即处置，黄色为限时整改，Slate 为已完成推理后的无违规，Unknown 为尚无结论。

### Cards / Containers

- **Corner Style:** 4px 或直角，由裁切和规则线建立层级。
- **Background:** Proof White 用于签派条与处置单，Graphite 用于影像舞台。
- **Shadow Strategy:** 只有主证据、主处置面和抽屉使用已命名的环境阴影。
- **Border:** 1px 规则线；签派条以 5px 石墨顶部线强调结构。

### Inputs / Fields

- **Style:** 标签在上，白色或透明纸面，1px 规则线，最小高度 44px。
- **Focus:** 钴蓝双环或底边；隐藏文件输入通过父级 `focus-within` 显示焦点。
- **Error / Disabled:** 错误必须说明问题和恢复动作；占位符使用加深次级墨色，不代替标签。

### Navigation

桌面为 76px 顶部栏，五项业务能力各自占据稳定列。当前项使用淡钴蓝纸面与 4px 下划线；悬停只改变表面和文字，不移动布局。移动端导航进入第二行并隐藏图标，中文标签保持单行。

### Evidence Stage

石墨舞台包含证据名称、上传或视图切换、完整影像、定位框和底部事实栏。图片检测用原图 / AI 标注切换和目标联系条；实时检测用浏览器视频与检测框叠加；视频页使用同一舞台语言承载输入、进度和结果。

### Dispatch Strip and Contact Sheet

签派条把上下文、准备状态、系统状态和主动作排成一张可执行单据。联系表以真实缩略影像作为记录入口，并用风险、来源、负责人和时间建立扫描顺序；选中记录驱动右侧处置单，不再退回传统宽数据表。

### Notification Drawer

通知设置从右侧进入，显示官方群验证结果、本机名称、安全短编号和启用状态，不回显 webhook、token 或完整会话 ID。抽屉打开后焦点进入内部并形成 Tab 圈闭，Escape 关闭，关闭后焦点返回触发器。

## Do's and Don'ts

### Do:

- **Do** 让真实证据占据页面最大视觉面积，并让主要动作贴近证据。
- **Do** 复用顶部导航、证据舞台、签派条、联系表和处置单这一套语言。
- **Do** 将监测状态、业务风险、存储错误和通知恢复分别说明。
- **Do** 在移动端保持“上下文、证据、动作、明细”的任务顺序。
- **Do** 使用原生语义控件、44px 操作高度、可见焦点和减少动态效果回退。

### Don't:

- **Don't** 恢复深色侧栏、四格状态轨或同尺寸统计卡片墙。
- **Don't** 使用渐变、玻璃拟态、霓虹发光、装饰铆钉、警戒条纹或表情符号。
- **Don't** 用红黄表示导航、普通按钮、摄像头连接或系统错误。
- **Don't** 用模型文件名、帧计数和技术参数挤占第一视口。
- **Don't** 把视频逐帧累计描述为独立人员或处置事件。
