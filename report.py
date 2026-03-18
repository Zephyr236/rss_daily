
import os
import smtplib
from openai import OpenAI
import time
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta
import html
import json
from typing import List, Dict, Optional
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import markdown

# 全局配置
CONFIG = {
    'PROXY': {
        'http': os.getenv('PROXY_HTTP', 'socks5h://127.0.0.1:10909'),
        'https': os.getenv('PROXY_HTTPS', 'socks5h://127.0.0.1:10909')
    },
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY', ''),
    'OPENAI_BASE_URL': os.getenv('OPENAI_BASE_URL', ''),
    'OPENAI_MODEL': os.getenv('OPENAI_MODEL', ''),
    'EMAIL': {
        'SMTP_SERVER': os.getenv('SMTP_SERVER', 'smtp.qq.com'),
        'SMTP_PORT': int(os.getenv('SMTP_PORT', 456)),
        'USERNAME': os.getenv('EMAIL_USERNAME', ''),
        'PASSWORD': os.getenv('EMAIL_PASSWORD', ''),
        'FROM_EMAIL': os.getenv('FROM_EMAIL', ''),
        'TO_EMAILS': os.getenv('TO_EMAILS', '').split(',')
    },
    'USE_PROXY': os.getenv('USE_PROXY', 'false').lower() == 'true',
    'DAYS_TO_INCLUDE': int(os.getenv('DAYS_TO_INCLUDE', 2)),  # 默认包含今天和昨天
    'MAX_WORKERS': int(os.getenv('MAX_WORKERS', 50)),
    'OPML_FILE': os.getenv('OPML_FILE', 'rss.txt'),
    'DATE_PARSING': {
        'USE_DATEUTIL': os.getenv('USE_DATEUTIL', 'true').lower() == 'true',  # 是否使用dateutil作为后备
        'STRICT_TIMEZONE': os.getenv('STRICT_TIMEZONE', 'true').lower() == 'true',  # 是否严格处理时区
        'DEFAULT_TIMEZONE': os.getenv('DEFAULT_TIMEZONE', 'UTC'),  # 默认时区
        'INCLUDE_TODAY': os.getenv('INCLUDE_TODAY', 'true').lower() == 'true',  # 是否包含今天
        'ALLOW_NO_DATE': os.getenv('ALLOW_NO_DATE', 'true').lower() == 'true',  # 是否允许无日期条目
        'DEBUG': os.getenv('DATE_PARSING_DEBUG', 'false').lower() == 'true',  # 调试模式，输出详细日志
    },
    'NETWORK': {
        'MAX_RETRIES': int(os.getenv('NETWORK_MAX_RETRIES', 3)),  # 最大重试次数
        'TIMEOUT': int(os.getenv('NETWORK_TIMEOUT', 30)),  # 请求超时时间（秒）
        'VERIFY_SSL': os.getenv('NETWORK_VERIFY_SSL', 'false').lower() == 'true',  # 是否验证SSL证书
        'USER_AGENT': os.getenv('NETWORK_USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36'),
    }
}

def generate_report_with_ai(prompt, output_file, max_retries=5):
    """使用AI模型生成日报并保存，添加重试机制"""
    try:
        client = OpenAI(
            api_key=CONFIG['OPENAI_API_KEY'],
            base_url=CONFIG['OPENAI_BASE_URL']
        )
    except Exception as e:
        print(f"初始化AI客户端失败: {e}")
        return False
    
    for attempt in range(max_retries):
        try:
            print(f"正在使用大语言模型生成日报... (尝试 {attempt + 1}/{max_retries})")
            
            response = client.chat.completions.create(
                model=CONFIG['OPENAI_MODEL'],
                messages=[
                    {"role": "system", "content": """你是一名资深的行业分析师和新闻编辑，具备以下专业能力：

## 核心专长
- 深度分析各垂直领域的技术趋势、市场动态和行业发展
- 快速识别新闻价值层级，准确判断信息重要性
- 擅长从海量信息中提取关键洞察和潜在影响
- 具备敏锐的商业嗅觉，能发现行业机会和挑战

## 分析原则
1. **价值优先**：优先关注对行业产生重大影响的事件
2. **多维度视角**：从技术、商业、政策、用户等多角度分析
3. **趋势洞察**：识别短期波动背后的长期趋势
4. **实用导向**：提供对读者决策有价值的信息和建议

## 输出标准
- 内容准确性高，逻辑清晰严谨
- 语言专业但易懂，适合行业从业者阅读
- 结构化呈现，便于快速获取关键信息
- 保持客观中立，基于事实进行分析

请基于这些专业标准，为用户生成高质量的行业日报。"""},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
            )
            
            content = response.choices[0].message.content
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"日报已生成并保存至 {output_file}")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"生成日报失败: {e}")
            
            if True:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt * 30
                    print(f"遇到速率限制，等待 {wait_time} 秒后重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    print("达到最大重试次数，仍然遇到速率限制")
            else:
                print(f"遇到非速率限制错误，停止重试")
                break
    
    return False


def markdown_to_html(markdown_content):
    """将Markdown内容转换为HTML格式，添加基本样式"""
    # 配置markdown扩展
    extensions = ['tables', 'fenced_code', 'toc']
    
    # 转换markdown到HTML
    html_content = markdown.markdown(markdown_content, extensions=extensions)
    
    # 添加CSS样式
    styled_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f8f9fa;
            }}
            .container {{
                background-color: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
                margin-bottom: 30px;
            }}
            h2 {{
                color: #34495e;
                border-left: 4px solid #3498db;
                padding-left: 15px;
                margin-top: 30px;
                margin-bottom: 15px;
            }}
            h3 {{
                color: #7f8c8d;
                margin-top: 25px;
                margin-bottom: 10px;
            }}
            a {{
                color: #3498db;
                text-decoration: none;
            }}
            a:hover {{
                text-decoration: underline;
            }}
            code {{
                background-color: #f1f2f6;
                padding: 2px 6px;
                border-radius: 3px;
                font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            }}
            pre {{
                background-color: #2f3640;
                color: #f5f6fa;
                padding: 15px;
                border-radius: 5px;
                overflow-x: auto;
            }}
            blockquote {{
                border-left: 4px solid #bdc3c7;
                margin: 20px 0;
                padding-left: 15px;
                color: #7f8c8d;
            }}
            table {{
                border-collapse: collapse;
                width: 100%;
                margin: 20px 0;
            }}
            th, td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}
            th {{
                background-color: #f8f9fa;
                font-weight: bold;
            }}
            .highlight {{
                background-color: #fff3cd;
                padding: 10px;
                border-radius: 5px;
                border-left: 4px solid #ffc107;
                margin: 15px 0;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #eee;
                color: #7f8c8d;
                font-size: 14px;
            }}
            .report-section {{
                border: 1px solid #eee;
                border-radius: 5px;
                padding: 20px;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            {html_content}
            <div class="footer">
                <p>本邮件由RSS日报生成器自动发送 | 生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return styled_html


def combine_reports_to_html(report_files):
    """将所有日报合并为一个HTML文档"""
    combined_content = ""
    
    for report_file in report_files:
        try:
            # 读取Markdown内容
            with open(report_file, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
            
            # 提取领域名称
            filename = os.path.basename(report_file)
            parts = filename.replace('.md', '').split('_')
            if len(parts) >= 3:
                domain = parts[0]
            else:
                domain = "RSS"
            
            # 添加分隔线和领域标题
            combined_content += f"\n\n---\n\n<h1>{domain}领域日报</h1>\n\n"
            combined_content += markdown_content
            
        except Exception as e:
            print(f"读取日报文件 {report_file} 时出错: {e}")
            continue
    
    return combined_content


def send_combined_email_report(report_files):
    """发送合并后的日报邮件给所有收件人"""
    if not CONFIG['EMAIL']['USERNAME'] or not CONFIG['EMAIL']['PASSWORD']:
        print("邮件配置不完整，跳过邮件发送")
        return False
    
    if not CONFIG['EMAIL']['TO_EMAILS']:
        print("未配置收件人邮箱，跳过邮件发送")
        return False
    
    if not report_files:
        print("没有日报文件需要发送")
        return False
    
    try:
        # 合并所有日报内容
        combined_markdown = combine_reports_to_html(report_files)
        
        if not combined_markdown:
            print("合并日报内容失败")
            return False
        
        # 转换为HTML
        html_content = markdown_to_html(combined_markdown)
        
        today = datetime.now().strftime("%Y年%m月%d日")
        days_desc = f"近{CONFIG['DAYS_TO_INCLUDE']}天" if CONFIG['DAYS_TO_INCLUDE'] > 1 else "当日"
        
        # 创建纯文本版本（备用）
        text_content = f"""
RSS日报汇总 - {today}

本邮件包含{days_desc}的最新资讯。

如果您无法正常查看HTML格式，请使用支持HTML的邮件客户端。

详细内容请查看HTML版本。

---
本邮件由RSS日报生成器自动发送
生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        """
        
        success_count = 0
        failed_count = 0
        
        # 为每个收件人单独建立SMTP连接
        for to_email in CONFIG['EMAIL']['TO_EMAILS']:
            try:
                # 为每个收件人创建独立的SMTP连接
                server = smtplib.SMTP_SSL(CONFIG['EMAIL']['SMTP_SERVER'])
                server.login(CONFIG['EMAIL']['USERNAME'], CONFIG['EMAIL']['PASSWORD'])
                
                # 创建邮件对象
                msg = MIMEMultipart('alternative')
                msg['From'] = CONFIG['EMAIL']['FROM_EMAIL'] or CONFIG['EMAIL']['USERNAME']
                msg['To'] = to_email
                msg['Subject'] = f"RSS日报汇总 - {today} ({days_desc}内容)"
                
                # 添加纯文本和HTML版本
                text_part = MIMEText(text_content, 'plain', 'utf-8')
                html_part = MIMEText(html_content, 'html', 'utf-8')
                
                msg.attach(text_part)
                msg.attach(html_part)
                
                # 发送邮件
                server.sendmail(msg['From'], to_email, msg.as_string())
                server.quit()  # 立即关闭连接
                
                print(f"[OK] 日报已成功发送到 {to_email}")
                success_count += 1
                time.sleep(2)  # 避免发送过快
            except Exception as e:
                print(f"[ERROR] 发送邮件到 {to_email} 失败: {e}")
                failed_count += 1
        
        print(f"\n邮件发送完成: 成功 {success_count} 个, 失败 {failed_count} 个")
        return success_count > 0
        
    except Exception as e:
        print(f"[ERROR] 发送合并日报邮件失败: {e}")
        return False
    
def load_json_content(json_file_path):
    """加载JSON文件内容"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载JSON文件 {json_file_path} 时出错: {e}")
        return []

def generate_daily_report_prompt(rss_dir="./rss_data"):
    """读取rss目录下的JSON文件，分析内容，生成日报提示词并直接调用AI生成日报"""
    if not os.path.exists(rss_dir):
        print(f"错误: {rss_dir} 目录不存在")
        return []
        
    files = [f for f in os.listdir(rss_dir) if os.path.isfile(os.path.join(rss_dir, f)) and f.endswith('.json')]
    
    if not files:
        print("没有找到 JSON 文件进行处理")
        return []
        
    print(f"找到 {len(files)} 个 JSON 文件，开始生成日报...")
    
    output_dir = "./daily_reports"
    os.makedirs(output_dir, exist_ok=True)
    
    reports_dir = "./generated_reports"
    os.makedirs(reports_dir, exist_ok=True)
    
    success_count = 0
    failed_count = 0
    report_files = []
    
    for file_name in files:
        file_path = os.path.join(rss_dir, file_name)
        
        json_data = load_json_content(file_path)
        
        if not json_data:
            print(f"JSON文件 {file_name} 为空或读取失败")
            continue
            
        source_count = len(json_data['source'].split(","))
        item_count = len(json_data['items'])
        
        links = [item.get('link', '') for item in json_data['items'] if item.get('link')]
        link_count = len(set(links))
        
        today = datetime.now().strftime("%Y年%m月%d日")
        today_file = datetime.now().strftime("%Y%m%d")
        
        group_name = os.path.splitext(file_name)[0]
        
        days_desc = f"近{CONFIG['DAYS_TO_INCLUDE']}天" if CONFIG['DAYS_TO_INCLUDE'] > 1 else "当日"
        
        prompt = f"""# {group_name}领域日报 ({today})

## 背景信息
- 本日报基于{source_count}个RSS信息源
- 包含{item_count}个独立新闻项目
- 包含约{link_count}个独立链接
- 所有内容均为{days_desc}发布的资讯

## 分析要求（重要！）
你必须仔细分析所有{item_count}个新闻项目，不要遗漏任何一条。请注意：
1. 即使内容相似，也要考虑每个独立来源的报道角度
2. 对于重要新闻，需关注多个来源的不同观点
3. 必须处理提供的所有{item_count}个项目，不可跳过
4. 处理完成后，请检查你是否涵盖了所有主要项目

## 您的任务
请阅读以下JSON格式的RSS内容，生成一份高质量的{group_name}领域日报，要求：

1. 首先提供一段简短的总结，概述{days_desc}该领域的主要动态和趋势
2. 将新闻按主题或子领域分类，使用二级标题组织内容
3. 对每条重要新闻提供简洁的摘要和分析
4. 保留重要新闻的原文链接，格式为 [标题](链接)
5. 如有重大事件、新产品发布或重要观点，请特别标注
6. 使用markdown格式，确保排版清晰易读
7. 在日报末尾，提供一个"数据统计"部分，说明你分析了多少新闻项目，如何进行的分析

## RSS源内容（JSON格式）
```json
{json.dumps(json_data, ensure_ascii=False, indent=2)}
```

请基于以上{item_count}个新闻项目，创建一份专业、信息密度高的{group_name}日报。注重提取有价值的信息，避免冗余内容，让读者能够快速了解{days_desc}该领域的重要动态。记住，你需要分析所有{item_count}个项目，确保全面覆盖。
"""
        
        prompt_file = os.path.join(output_dir, f"{group_name}_prompt.txt")
        with open(prompt_file, 'w', encoding='utf-8') as f:
            f.write(prompt)
            
        print(f"已生成 {group_name} 的日报提示词，保存至 {prompt_file}")
        
        output_file = os.path.join(reports_dir, f"{group_name}_{today_file}_日报.md")
        
        print(f"正在为 {group_name} 生成日报...")
        if generate_report_with_ai(prompt, output_file):
            success_count += 1
            report_files.append(output_file)
            print(f"[OK] {group_name} 日报生成成功")
        else:
            failed_count += 1
            print(f"[ERROR] {group_name} 日报生成失败")
    
    print("\n日报生成任务完成!")
    print(f"成功: {success_count} 个, 失败: {failed_count} 个")
    print(f"生成的日报保存在 {reports_dir} 目录中")
    

    return report_files
