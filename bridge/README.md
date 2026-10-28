# HaloBridge（花再 Halo PixelBar 歌词桥）

配套 Folia 模组 **Halo PixelBar 歌词** 使用。模组负责选歌词，这个程序负责把文字写进音响的点阵屏，
并在 Folia 关闭后把屏幕还原成时钟待机界面。

## 最省事的用法（推荐）

下载 `dist/HaloBridge.exe`（约 8 MB，**不需要装 Python**）。

1. 放到一个不会被移动的目录，例如 `D:\HaloBridge\HaloBridge.exe`
2. 双击运行一次，确认没有报错（它没有窗口，进程会在后台）
3. 把这个 exe 的**快捷方式**放进启动文件夹，开机自动挂上：

   ```
   %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
   ```

它自己会看 Folia 在不在：

- Folia 打开 → 接管点阵屏，显示歌词
- Folia 关闭 → 先把屏幕还原成时钟，再停止写入
- 已经在运行时不重复启动（端口占用即退出）

## 冲突

**关闭 EDIFIER TempoHub。** 两个程序抢同一个 HID 通道，同时运行会乱跳。

## 从源码运行（可选）

需要 Python 3.9+：

```bat
install_bridge.bat     :: 建 venv + 装 hidapi
python halo_agent.py   :: 或者 pythonw halo_agent.py 无窗口
```

旧的两段式脚本仍保留：`halo_bridge.py`（HID 写入）+ `watch_folia.py`（看门狗）。
新代码合并成 `halo_agent.py` 一个进程，退出还原更可靠。

## 排查

- 屏幕没反应：先看 `http://127.0.0.1:8765/state` 能不能 POST 通；再看音响是否用 USB 连着
- `hidapi` 装不上：换 pip 源，例如 `-i https://mirrors.aliyun.com/pypi/simple/`
- 有多个 Halo 设备：程序按 VID `2D99` / PID `A106` 匹配
- 想看日志：用 `python halo_agent.py` 从控制台跑

## 协议

64 字节 HID 写入，帧头 `2E AA EC E8`（文本）/ `2E AA EC EF`（布局与 UI 模式），
颜色 + 长度 + UTF-8 文本 + 校验（参考 HaloPixelToolBox / HaloLyricSync 的开源实现）。
