# 中文字体文件

本项目使用 **Noto Sans CJK SC** (思源黑体) 作为中文字体，由 Google 和 Adobe 联合开发的开源字体。

## 字体文件

- `NotoSansCJK-Regular.ttc` - 常规体 (约 19MB)
- `NotoSansCJK-Bold.ttc` - 粗体 (约 20MB)

## 下载方式

### 方式 1: 从系统字体复制 (推荐，Linux)

如果系统已安装 Noto CJK 字体：

```bash
# 创建 fonts 目录
mkdir -p fonts

# 复制字体文件
cp /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc fonts/
cp /usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc fonts/
```

### 方式 2: 从 Google Fonts 下载

```bash
# 使用 git clone (字体在 noto-cjk 仓库)
git clone https://github.com/googlefonts/noto-cjk.git --depth 1
cp noto-cjk/Sans/OTF/SimplifiedChinese/NotoSansSC-Regular.otf fonts/
cp noto-cjk/Sans/OTF/SimplifiedChinese/NotoSansSC-Bold.otf fonts/
```

### 方式 3: 直接下载

从以下地址下载：
- [Noto Sans CJK SC GitHub](https://github.com/googlefonts/noto-cjk)
- [Google Fonts - Noto Sans SC](https://fonts.google.com/noto/specimen/Noto+Sans+SC)

## 配置

在 `.env` 文件中设置：

```env
QBOT_FONT_PATH=fonts/NotoSansCJK-Regular.ttc
```

## 许可证

SIL Open Font License 1.1
详情查看：https://scripts.sil.org/OFL
