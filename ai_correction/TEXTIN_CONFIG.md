# Textin API 配置说明

## 📋 配置信息

已为项目配置 Textin 图片优化 API 凭证：

```ini
TEXTIN_APP_ID=1f593ca1048d5c8f562a7ee1a82d0f0b
TEXTIN_SECRET_CODE=4233796c5b4d7d263ea79c46f10acb1c
TEXTIN_API_URL=https://api.textin.com/ai/service/v1/crop_enhance_image
```

## 🔧 配置方法

### 方法 1: 使用 `.env` 文件（推荐，已配置）

✅ **已完成配置**：Textin API 凭证已添加到 `ai_correction/.env` 文件中。

如需手动修改，编辑 `.env` 文件中的以下部分：

```ini
# ============ Textin图片优化API配置 ============
TEXTIN_APP_ID=1f593ca1048d5c8f562a7ee1a82d0f0b
TEXTIN_SECRET_CODE=4233796c5b4d7d263ea79c46f10acb1c
TEXTIN_API_URL=https://api.textin.com/ai/service/v1/crop_enhance_image
```

### 方法 2: 系统环境变量

在 Windows PowerShell 中设置：

```powershell
$env:TEXTIN_APP_ID="1f593ca1048d5c8f562a7ee1a82d0f0b"
$env:TEXTIN_SECRET_CODE="4233796c5b4d7d263ea79c46f10acb1c"
$env:TEXTIN_API_URL="https://api.textin.com/ai/service/v1/crop_enhance_image"
```

### 方法 3: Railway/部署平台环境变量

在部署平台的环境变量配置页面添加：

- `TEXTIN_APP_ID` = `1f593ca1048d5c8f562a7ee1a82d0f0b`
- `TEXTIN_SECRET_CODE` = `4233796c5b4d7d263ea79c46f10acb1c`
- `TEXTIN_API_URL` = `https://api.textin.com/ai/service/v1/crop_enhance_image`

## ✅ 验证配置

### 1. 快速测试

```bash
cd ai_correction
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print('TEXTIN_APP_ID:', os.getenv('TEXTIN_APP_ID'))
print('TEXTIN_SECRET_CODE:', os.getenv('TEXTIN_SECRET_CODE')[:10] + '...')
print('配置加载成功!' if os.getenv('TEXTIN_APP_ID') else '配置未找到')
"
```

### 2. 测试 API 连接

```bash
cd ai_correction
python -c "
from functions.image_optimization.textin_client import TextinClient
client = TextinClient()
status = client.check_api_status()
print('API 状态:', '✅ 可用' if status else '❌ 不可用')
"
```

### 3. 完整功能测试

准备一张测试图片（如 `test.jpg`），然后运行：

```bash
cd ai_correction
python -c "
from functions.image_optimization.image_optimizer import ImageOptimizer
from functions.image_optimization.models import OptimizationSettings

optimizer = ImageOptimizer(settings=OptimizationSettings.get_preset('smart'))
result = optimizer.optimize_image('test.jpg')

if result.success:
    print('✅ 优化成功!')
    print(f'原图: {result.original_path}')
    print(f'优化后: {result.optimized_path}')
else:
    print(f'❌ 优化失败: {result.error_message}')
"
```

## 🔍 常见问题

### Q1: 提示 "Textin API凭证未配置"
**解决**: 确保 `.env` 文件存在且内容正确，或使用方法 2/3 设置环境变量。

### Q2: API 调用返回 401 错误
**解决**: 检查 `TEXTIN_APP_ID` 和 `TEXTIN_SECRET_CODE` 是否正确，注意不要有多余空格。

### Q3: 网络连接失败
**解决**: 
- 检查网络连接
- 确认防火墙未阻止访问 `api.textin.com`
- 尝试使用代理（如需要）

### Q4: 图片优化失败但不影响批改
**说明**: 这是正常的容错机制，系统会自动降级使用原图继续批改流程。

## 📊 API 使用限制

根据 Textin 官方文档：
- **免费额度**: 通常有每日调用次数限制
- **并发限制**: 建议不超过 5 个并发请求
- **文件大小**: 单张图片不超过 10MB
- **超时时间**: 默认 30 秒

## 🔒 安全提示

⚠️ **重要**: 
- `.env` 文件已被 `.gitignore` 忽略，不会提交到 Git
- 不要将 API 密钥硬编码到代码中
- 不要在公开渠道分享 `TEXTIN_SECRET_CODE`
- 定期轮换 API 密钥以提高安全性

## 📚 相关文档

- [Textin 官方文档](https://www.textin.com/document)
- [图片优化模块说明](./API配置说明.md)
- [上传功能总结](./UPLOAD_FEATURE_SUMMARY.md)

---

**最后更新**: 2025-11-23  
**配置状态**: ✅ 已就绪

