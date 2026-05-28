# 🌟 AstrBot Plugin: Checkin Game

![AstrBot](https://img.shields.io/badge/AstrBot-Plugin-blue.svg) 
![Python](https://img.shields.io/badge/Python-3.8+-yellow.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

一款专为 [AstrBot](https://github.com/Soulter/AstrBot) 打造的重度互动插件。集**极简高定 UI、多群独立数据、硬核经济博弈（抢劫/行侠仗义）** 于一体，让你的群聊瞬间活跃起来！

---

## ✨ 核心特性

- 🎨 **拟态高定 UI**：采用 Pillow 纯手绘。拥有动态自适应图片比例、高斯模糊柔和阴影、大圆角卡片，完美复刻 iOS 原生质感的个人资料卡与签到卡片。
- 🖼️ **智能随机图与本地盲盒**：内置多个高可用二次元随机图 API，突破防盗链限制。更支持建立本地 `bg_images` 图库，实现零延迟、永不失效的秒级出图。
- 🎭 **高度自定义图标**：彻底告别 Emoji 乱码！UI 底部社交图标和互动图标均支持替换为自定义透明 PNG 图片。
- 👑 **真实群等级联动**：自动调用底层接口，资料卡可直接读取并显示用户真实的 QQ 群等级（如 `LV59`）与群头衔。
- 💰 **硬核群聊经济学**：
  - 签到积累基础积分。
  - 刺激的 `/抢劫` 系统：动态计算劫金上限（受限于受害者余额），连续 5 天作案将获得【通缉犯】红名标识。
  - 博弈的 `/行侠仗义` 玩法：抢劫发生 3 分钟内可介入，成功可获系统奖励，失败不仅救人不成，还会被反抢。
- 🔒 **多群数据隔离**：彻底分离不同群聊的资产与排行榜，绝不串数据，并支持在控制台指定特定群聊开启。

---

## 📸 界面预览

<img width="704" height="446" alt="image" src="https://github.com/user-attachments/assets/23a72bc0-abab-406a-b1b0-71f04785eea2" />

<img width="677" height="465" alt="image" src="https://github.com/user-attachments/assets/1e80940a-8868-408a-9fd8-09bb9c8cbaa0" />

<img width="500" height="920" alt="c30308c8168ba88c4f45f7ef38c92fbb" src="https://github.com/user-attachments/assets/1ed4f554-0e30-4935-a146-28e4b83b063a" />




| 每日签到 | 个人资料卡 | 财富排行榜 |
| :---: | :---: | :---: |
| <img src="docs/checkin.jpg" width="250"/> | <img src="docs/profile.jpg" width="250"/> | <img src="docs/leaderboard.jpg" width="250"/> |

---

## 📦 安装与配置

### 1. 安装插件
**推荐方式**：在 AstrBot 网页控制台的【插件市场】搜索 `checkin_game` 进行一键安装。

**手动安装**：在终端进入 AstrBot 的插件目录并克隆本仓库：
```bash
cd AstrBot/data/plugins
git clone [https://github.com/你的用户名/astrbot_plugin_checkin_game.git](https://github.com/你的用户名/astrbot_plugin_checkin_game.git)
```

### 2. 安装可选依赖 (极度推荐)
为了让群友昵称中的 Emoji 表情完美显示在图片上而不变成方块，请在 AstrBot 的 Python 环境中安装微型表情库：
```bash
pip install pilmoji
```

### 3. 使用控制台配置
安装完成后，**重启 AstrBot**。
进入 AstrBot 网页管理后台 -> 🟢 **设置图标 (插件配置)**，你可以直接通过可视化界面修改所有核心数值：
- `admin_qq`：设置拥有直接加减积分权限的超级管理员 QQ。
- `enabled_groups`：设置插件只在哪些群运行（留空则所有群开启）。
- 修改各项经济数值：抢劫失败率、行侠仗义奖励、通缉犯罚金等。

---

## 🚀 指令大全

| 指令格式 | 权限 | 功能说明 |
| --- | --- | --- |
| `签到` 或 `/签到` | 所有人 | 每日签到，获取随机语录和 1 个基础积分。 |
| `/我的积分` | 所有人 | 生成并查看自己的 Ins 拟态风格个人资产资料卡。 |
| `/排行榜` | 所有人 | 生成本群前 10 名富豪榜单（显示红名通缉犯专属标识）。 |
| `/抢劫 @目标` | 所有人 | 尝试夺取目标积分。有概率失败；连续 5 天作案将获得红名。 |
| `/行侠仗义` | 所有人 | 在有人发起抢劫的 3 分钟内输入，有概率阻止抢劫并获赏，失败则自己掉积分。 |
| `/财富加 @目标 30` | 管理员 | (后台指令) 为指定用户增加 30 积分。 |
| `/财富减 @目标 30` | 管理员 | (后台指令) 扣除指定用户 30 积分（扣底为 0）。 |

---

## 🎨 高级进阶：UI 深度定制

本插件的 UI 拥有极高的自由度。所有的自定义文件只需直接放入本插件目录 (`AstrBot/data/plugins/astrbot_plugin_checkin_game/`) 中即可，**无需修改任何代码**：

### 1. 自定义本地随机背景图库
在插件目录下新建名为 `bg_images` 的文件夹，向其中放入任何 `.png`, `.jpg`, `.webp` 图片。
> **效果**：系统将优先且随机抽取这里的图片作为背景。速度极快且完全防盗链！

### 2. 纯净矢量图标替换
准备透明背景的 `.png` 图标，并重命名为以下指定名称放入插件根目录：
- **资料卡底部图标**：`icon_ins.png` / `icon_x.png` / `icon_web.png`
- **签到卡交互图标**：`icon_like.png` (点赞) / `icon_comment.png` (评论) / `icon_share.png` (转发) / `icon_bookmark.png` (收藏)
> **效果**：系统会自动将它们加载到卡片上。如果未提供，系统会自动优雅降级为极简占位符，绝不报错。

### 3. 自定义中文字体
插件默认附带了一款基础开源字体。如果你想使用自己的字体，只需将喜欢的 `.ttf` 字体文件重命名为 `AlibabaPuHuiTi-2-65-Medium.ttf` 并覆盖原文件，即可瞬间改变整个插件的文字排版风格。

---

## 📄 License
MIT License
