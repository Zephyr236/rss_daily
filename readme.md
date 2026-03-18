# RSS 日报生成器

这是一个功能增强的 RSS 日报生成器，支持今天和昨天的内容筛选、AI 生成日报、自动邮件发送，并完美适配 GitHub Actions 环境。

## 🚀 主要特性

- **智能日期筛选**：不仅筛选当天内容，还保留昨天的重要资讯
- **AI 驱动分析**：使用大语言模型生成高质量、结构化的日报
- **自动邮件发送**：生成日报后自动发送到指定邮箱
- **GitHub Actions 支持**：每天自动生成并发送日报
- **多种邮件服务商**：支持 Gmail、Outlook、QQ邮箱等
- **代理支持**：支持通过代理访问 RSS 源
- **灵活配置**：通过环境变量轻松配置各种参数

## 📁 文件说明

- `rssdaily.py` - 主程序文件（优化版单文件）
- `.github/workflows/daily-report.yml` - GitHub Actions 主工作流
- `CONFIG.md` - 详细配置说明

## 🛠 快速开始

### 1. 准备工作

1. Fork 本仓库到您的 GitHub 账户
2. 准备您的 RSS 订阅源 OPML 文件，命名为 `rss.txt` 放在仓库根目录
3. 获取 OpenAI API 密钥

### 2. 配置环境变量

在 GitHub 仓库的 `Settings -> Secrets and variables -> Actions` 中添加：

**必需配置：**
```
OPENAI_API_KEY=your_openai_api_key
EMAIL_USERNAME=your_email@gmail.com  
EMAIL_PASSWORD=your_app_password
TO_EMAILS=recipient@email.com
```

**可选配置：**
```
DAYS_TO_INCLUDE=2          # 包含天数（默认今天+昨天）
USE_PROXY=false            # 是否使用代理
SMTP_SERVER=smtp.gmail.com # SMTP 服务器
```

### 3. 测试运行

1. 进入 Actions 页面
2. 选择 "Test RSS Report Generator" 工作流  
3. 点击 "Run workflow" 手动测试
4. 查看执行结果和生成的报告

### 4. 启用定时任务

配置完成后，工作流将在每天北京时间上午 9 点自动运行。

## 🔧 本地运行

```bash
# 安装依赖
pip install requests[socks] tqdm beautifulsoup4 openai

# 设置环境变量
export OPENAI_API_KEY="your_key"
export EMAIL_USERNAME="your_email"
export EMAIL_PASSWORD="your_password"  
export TO_EMAILS="recipient@email.com"

# 运行程序
python optimized_rss_daily_report.py
```

## 📊 主要改进

相比原版本，优化版本具有以下改进：

1. **扩展日期范围**：从只筛选当天改为包含今天和昨天（可配置）
2. **邮件发送功能**：集成完整的邮件发送模块，支持多种邮件服务商  
3. **环境变量配置**：所有配置项都支持环境变量，便于 CI/CD 部署
4. **GitHub Actions 优化**：专门为 GitHub Actions 环境优化，支持定时任务
5. **错误处理增强**：更好的异常处理和重试机制
6. **模块化设计**：代码结构更清晰，便于维护和扩展

## 📧 邮件配置示例

### Gmail 配置
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USERNAME=youremail@gmail.com
EMAIL_PASSWORD=your_16_char_app_password  # 应用专用密码
```

### QQ 邮箱配置  
```
SMTP_SERVER=smtp.qq.com
SMTP_PORT=587
EMAIL_USERNAME=youremail@qq.com
EMAIL_PASSWORD=your_authorization_code    # 授权码
```

## 🔄 工作流程

1. **RSS 采集**：并发获取所有 RSS 源的最新内容
2. **日期筛选**：保留指定天数内的文章（默认今天+昨天）
3. **内容清理**：移除 HTML 标签，提取纯文本内容
4. **AI 分析**：使用大语言模型生成结构化日报
5. **邮件发送**：将生成的日报发送到指定邮箱
6. **文件保存**：保存生成的报告文件供下载

## 📋 生成的文件

- `generated_reports/` - AI 生成的 Markdown 格式日报
- `daily_reports/` - AI 提示词文件
- `rss/` - 原始 RSS 数据文件（XML 和 JSON 格式）

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进这个项目！

## 📄 许可证

本项目采用 MIT 许可证。
