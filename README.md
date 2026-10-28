# Halo PixelBar 歌词（Folia 模组）

把 [Folia](https://github.com/chthollyphile/folia-major) 正在播放的歌词行，实时推到
**花再 Halo PixelBar** 音响的点阵屏上。

> 说明：Folia 自带的歌词只在电脑屏幕上炫；这个模组把同一份歌词发到音响的小屏。

---

## 功能

- **进度跟随**：按当前唱到的字算窗口位置，长句在屏上匀速滑动，不会越滚越落后
- **五种换行动画**：逐字打出 / 从右滑入 / 闪烁 / 双闪 / 擦除后重打
- **延迟补偿**：±2000ms，用于对齐 Folia 的歌词偏移
- **可调窗口**：每帧字数、滑动步长、帧间隔、文字布局（拉伸铺满 / 居中 / 靠左 / 靠右）
- **退出还原**：Folia 关闭后，屏幕自动回到时钟待机界面，不会停在最后一句歌词上

## 它怎么工作

```
Folia（Electron / Folium 模组）
   │  每 60ms 读 playback.getState() + lyrics.getLines()
   │  按播放进度算窗口，POST JSON
   ▼
http://127.0.0.1:8765/state
   ▼
HaloBridge（Python，配套程序）
   │  打包成 64 字节 HID 帧
   ▼
花再 Halo PixelBar 点阵屏（USB HID，VID 2D99 / PID A106）
```

模组本身**不直接写硬件**：Folia 的模组运行在渲染进程里，碰不到 USB HID。
所以需要一个本机桥接程序，两者用 HTTP 通信。

## 前置条件

| 项 | 要求 |
|---|---|
| 系统 | Windows |
| 音响 | 花再 Halo PixelBar，**USB 连接**（蓝牙只传音频，不传屏幕数据） |
| Python | 3.9+（装桥接程序用） |
| 冲突 | **必须关闭 EDIFIER TempoHub**，否则两个程序抢同一个 HID 通道，歌词会乱跳 |

## 安装

### 1. 装桥接程序

下载 `dist/HaloBridge-v1.0.0.zip`，解压到固定目录（例如 `D:\HaloBridge`），然后：

```bat
install_bridge.bat     :: 建 venv + 装 hidapi
start_bridge.bat       :: 手动测试（会带窗口，测完关掉）
```

日常使用不需要手动开：`watch_folia.py` 是看门狗，Folia 打开才启动桥接、Folia 关闭就结束桥接。
把它放进启动文件夹即可开机自启（平时不占资源）：

```
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
```

### 2. 装模组

把 `dist/halo-lyric-v1.0.0.zip` 拖进 Folia 的模组面板 → 「重载」→ 启用
「Halo PixelBar 歌词」→ 确认（未签名提示属正常）。

### 3. 放歌

Folia 放一首有歌词的歌，音响屏幕就开始显示。

## 设置

Folia → 设置 → 模组 → Halo PixelBar 歌词

| 设置 | 默认 | 说明 |
|---|---|---|
| 跟随播放进度 | 开 | 关掉则按固定节奏匀速滚 |
| 延迟补偿（毫秒） | 0 | 歌词比声音晚就填负数（如 −300），早就填正数 |
| 换行动画 | 逐字打出 | 五种进场效果 |
| 滑动帧间隔 | 220ms | 关闭跟随后生效 |
| 每帧位移 | 1 字 | 关闭跟随后生效 |
| 窗口字数 | 16 | 一屏几个字，拉伸布局下越多越扁 |
| 文字布局 | 拉伸铺满 | 拉伸 / 居中 / 靠左 / 靠右 |

## 目录结构

```
mod/       Folia 模组（mod.json、client.mjs）
bridge/    HaloBridge 桥接程序（Python）
dist/      发布包（两个 zip）与发布说明
```

## 已知限制

- 仅 Windows + Halo PixelBar（USB）
- 一帧最多约 50 字节 ≈ 16 个汉字，长句靠滑窗
- 点阵屏没有亮度通道，做不了淡入淡出
- 退出还原只能回到内置 UI 模式（时钟/游戏/工作…），无法还原 TempoHub 里的自定义壁纸图片

## 协议参考

64 字节 HID 写入，帧头 `2E AA EC E8`（文本）/ `2E AA EC EF`（布局与 UI 模式），
长度小端、UTF-8 文本、校验和 `acc = 128; for b: acc += b + 2; acc % 256`。

参考实现：[HaloPixelToolBox](https://github.com/XFEstudio/HaloPixelToolBox)、
[HaloLyricSync](https://github.com/nxz1026/HaloLyricSync)。

## License

未指定。使用或分发前请先联系作者。
