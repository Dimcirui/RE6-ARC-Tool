# RE6 ARC Tool (RE6 ARC Studio)

生化危机 6（PC）`.arc` 解包 / 预览 / 封包工具。界面参考 [ree-pak-gui](https://github.com/eigeen/ree-pak-gui)：左侧目录树，右侧详情 / 平铺两种视图，右侧预览面板，右键菜单。

## 运行

```bash
pip install -r requirements.txt
python app.py                 # 或双击 run.bat
python app.py some.arc dir/   # 启动时直接打开
```

需要 Python 3.10+，Windows 自带的 WebView2 运行时（Win10/11 已预装）。

## 打包成单个 exe

```bash
build.bat        # 输出 dist\RE6-ARC-Studio.exe（约 32 MB，无控制台窗口）
```

需要目标机器有 WebView2 运行时（Win10/11 已预装）。exe 未签名，个别杀毒软件或 SmartScreen 可能提示，属于 PyInstaller 单文件的常见情况。首次启动需要几秒解压。

## 功能

- **多归档工作区**：一次打开多个 `.arc` 或整个文件夹，跨归档搜索（空格分隔多个关键词，或 `.*` 切换正则）。
- **目录树 / 详情 / 平铺**：单子目录链自动折叠；平铺视图懒加载 TEX 缩略图；列可排序。
- **预览**：TEX 直接显示图片（含尺寸、mip、像素格式），其他文件显示十六进制。
- **提取**：选中项或当前过滤结果；贴图可选 *原样 .tex* / *DDS* / *PNG*；可放入以归档名命名的子文件夹。
- **封包（保守、可逆）**：
  - 保持原条目顺序；未改动的条目直接复用原压缩数据，不重新压缩。
  - 选择提取目录后“扫描差异”，只写入真正变化的文件；改好的 `.dds` 会自动写回原 `.tex`（保留其余头部字段，重算尺寸 / mip 偏移）。
  - 也可在浏览页右键：用文件替换、从归档删除、添加文件。
  - 保存为新 ARC，或覆盖原文件（自动保留一份 `.bak`）。
- **校验**：右键归档 → 校验完整性（逐条目 zlib 解压并核对大小）。
- 中文 / English，亮色 / 暗色。

## 格式说明（RE6 PC，version 7）

```
0x00 "ARC\0"   0x04 u16 version=7   0x06 u16 file_count
0x08 file_count × 0x50:  char[64] 路径(无扩展名, 反斜杠) | u32 类型哈希 | u32 压缩大小 | u32 (解压大小 | flags<<29) | u32 偏移
...  零填充到 0x8000 对齐，随后是紧密连续的 zlib 流
```

类型哈希 = `~crc32(资源类名) & 0x7FFFFFFF`（如 `rTexture` → `tex`）。档案里只存哈希；类名和扩展名用的是**游戏自己的**：
从 BH6.exe 里每个资源类的 DTI 和虚表提取（虚表 +0x18 返回的就是引擎读松散文件时用的扩展名），对应表见 `re6arc/arc.py` 的 `_ENGINE_CLASSES`。
零售档案里出现的 101 种类型全都有名字，例如 `rLinkUnit` → `lku`、`rBioSoundSequenceSe` → `bssq`。
所以解包出来的文件可以直接给 [RE6 Sideloader](https://github.com/Dimcirui/RE6-SideLoader) 侧载。
表里没有的哈希会以 8 位十六进制作为扩展名显示，并原样写回。

DDS 写回限制：像素格式必须与原 TEX 一致（DXT1 / DXT5 / BGRA8）；尺寸与 mip 数可以不同；不支持立方体贴图。

## 测试

```bash
python -m unittest discover -s tests -v
```

用环境变量 `RE6_ARC_DIR` 指向装有 RE6 PC `.arc` 的文件夹（如 `...\Resident Evil 6\nativePC\arc\DX9`）；找不到归档时测试会自动跳过。仓库不包含任何游戏资源。

测试覆盖：所有条目可解压、复用压缩流重建后与原文件**逐字节一致**、所有贴图 TEX→DDS→TEX **逐字节一致**、提取→比对→保存→重开的完整流程。

## 开发

`python app.py --dev` 在 `http://127.0.0.1:8765/?dev` 启动仅限本机回环的 HTTP 桥，可在普通浏览器里调试界面（原生对话框由 `POST /api/_dev_answer` 排队应答）。桌面版不使用它。前端错误会写入 `%APPDATA%\RE6ArcStudio\ui.log`。

## 目录

```
app.py            入口 (pywebview 窗口)
re6arc/arc.py     ARC 解析 / 重建
re6arc/tex.py     TEX 解析、预览解码、DDS 互转
re6arc/service.py 工作区、提取、暂存修改、比对、保存（无 GUI 依赖）
re6arc/api.py     暴露给前端的 API
ui/               前端 (原生 HTML/CSS/JS，无构建步骤)
tests/
```

## 致谢与声明

- 界面布局参考 [eigeen/ree-pak-gui](https://github.com/eigeen/ree-pak-gui)（未使用其代码）。
- ARC 结构与 TEX 头部字段经对照 [RE6-GUI-ARC-TOOL](https://github.com/Criticise/RE6-GUI-ARC-TOOL-by-CODEX-GPT-5.6-Sol-Terra) 的行为以及真实游戏归档交叉验证；本仓库代码为独立实现。
- 本项目为非官方的玩家社区工具，与 Capcom 无关。请只处理你合法拥有的游戏文件；仓库不包含任何游戏资源。
- 许可证：MIT，见 [LICENSE](LICENSE)。
