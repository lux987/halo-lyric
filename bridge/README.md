# HaloBridge（花再 Halo PixelBar 歌词桥）

配套 Folia 模组 **Halo PixelBar 歌词** 使用。模组负责选歌词，这个程序负责把文字写进音响的点阵屏。

## 安装

1. 确认已装 **Python 3.9+**（安装时勾选 “Add Python to PATH”）；
2. 把本目录放到一个不会被移动的位置，例如 `D:\HaloBridge`；
3. 双击 `install_bridge.bat`：会创建 `venv` 并安装 `hidapi`；
4. 双击 `start_bridge.bat` 可以手动测试一次（会弹一个窗口，测试完关掉）。

## 平时不用管它

`watch_folia.py` 是看门狗：

- Folia 打开时自动启动桥接（无窗口）
- Folia 关闭时自动结束桥接

把 `HaloBridge (Folia watchdog).lnk` 放进
`C:\Users\<你>\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`
即可开机自动挂上（只在 Folia 运行时才启动桥接，平时不占资源）。

## 冲突

**关闭 EDIFIER TempoHub。** 两个程序抢同一个 HID 通道，同时运行会乱跳。

## 排查

- 屏幕没反应：先看 `http://127.0.0.1:8765/state` 能不能 POST 通；再看音响是否用 USB 连着
- `hidapi` 装不上：换 pip 源，例如 `-i https://mirrors.aliyun.com/pypi/simple/`
- 有多个 Halo 设备：脚本按 VID `2D99` / PID `A106` 匹配

## 协议

64 字节 HID 写入，帧头 `2E AA EC E8`，颜色 + 长度 + UTF-8 文本 + 校验
（参考 HaloPixelToolBox / HaloLyricSync 的开源实现）。
