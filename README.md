# GradeOS 桌面测试版

桌面版和网页版共用同一份工作台、批改服务和 PDF 处理代码。安装包中带有 Electron、Python、Poppler、中文字体和运行依赖。Mac 版还包含编译好的 Vision 文字识别工具。

## 安装和使用

- **Windows x64**　双击 `Windows-x64-Setup.exe`。安装程序为当前用户创建开始菜单和桌面快捷方式，可以从系统的“已安装的应用”卸载。
- **Mac**　在苹果菜单的“关于本机”查看芯片。支持 macOS 13 及以上版本。Apple 芯片使用 `macOS-arm64.dmg`，Intel 处理器使用 `macOS-x64.dmg`。打开磁盘映像，将 GradeOS 拖到“应用程序”，再双击打开。
- 在「账号与设置」登录 GradeOS Cloud，可使用管理员分配的账号额度。新账号初始额度为零。也可选择「自带 API」填写自己的 OpenRouter 密钥或添加其他服务。模型服务会收到任务所需的文字或图像。
- 在「账号与设置」点「使用 Google 账号登录」，选好 Google 账号后会自动回到工作台。同一浏览器已有教师会话时可直接返回。已有账号首次使用可在 Cloud 门户用原密码登录并关联 Google，新教师可以用学校邀请码激活。
- Cloud 门户和兼容的云端接口可独立更新。本地工作台界面、批改服务和随包运行环境更新时，需要安装新版桌面包。
- 聊天默认提供 GPT-6.2 Sol、GPT-6.1 Terra、Gemini 4 Hydrogen、Gemini 4 Neon 和 Qwen4 Max。在「聊天模型」可勾选常用项。导入材料、查看结果和人工批注可在本地完成。
- 登录 Cloud 后，从批改结果打开「发布给学生」，选班级和收件人，核对学生可见内容后确认。使用自带 API 批改的结果也可以发布。
- 退出应用后再替换或安装新版。教师的资料和结果保存在当前用户的工作区，Mac 为 `~/Library/Application Support/GradeOS/workspace`，Windows 为 `%APPDATA%\GradeOS\workspace`。备份时先退出应用，再复制整个工作区。工作区可能包含模型连接凭据。
- 这些构建供测试使用。Mac 包采用临时签名，Windows 包尚未进行发行签名，系统或学校的设备管理策略可能提示或阻止打开。

## 从源码构建

构建机需要 Node 22.19 或更高版本（推荐 24）、npm、uv、支持 Zstandard 的 Python 3.14 及 curl。生成 Mac 镜像使用 macOS 的 Xcode 命令行工具和 hdiutil。生成 Windows 安装程序使用 NSIS 3 的 makensis。首次构建会下载校验过的运行环境。

从仓库根目录运行以下命令。每条构建命令生成一项产物，输出位于 `dist/desktop/`，旁边有 SHA-256 校验文件。

```sh
npm ci --prefix desktop --ignore-scripts
npm run desktop:build -- darwin-arm64
npm run desktop:build -- darwin-x64
npm run desktop:build -- win32-x64
npm run desktop:build -- source
```

Windows 构建机可直接生成 Windows 包。macOS 构建机可生成上述三种安装包。可用 `GRADEOS_BUILD_CACHE` 指定已校验下载文件的缓存位置。仓库的手动工作流“Desktop test installers”可分别在 Windows、Apple 芯片 Mac 和 Intel Mac 构建，并从安装后的应用执行检查。网页开发仍使用仓库原有的 `npm start` 入口。

## 从成品验证

先安装或将应用复制出磁盘映像，再运行对应命令。检查会新建独立工作区，导入合成矢量 PDF、重开工作区、导出带中文批注的 PDF，并让随包的批改进程完成离线预检。Mac 同时使用内置的 Vision 工具。所有材料均由检查程序生成。

```sh
node desktop/smoke.mjs "/Applications/GradeOS.app/Contents/MacOS/GradeOS"
```

```powershell
node desktop/smoke.mjs "$env:LOCALAPPDATA\Programs\GradeOS\app\GradeOS.exe"
```

GradeOS 代码采用 GPL-3.0-only。分发测试包时请一并提供对应版本的源码包。应用资源中的 `runtime/licenses`、`runtime/fonts/OFL.txt`、`runtime/upstream.json` 和第三方组件自带的声明记录了原始许可与来源。Poppler 的平台包和校验值见 `desktop/poppler.lock.json`，其上游代码和构建配方可从相应 conda-forge 包的 `info/recipe` 获取。Python 和 JavaScript 依赖固定于 `uv.lock` 及 `package-lock.json`。
