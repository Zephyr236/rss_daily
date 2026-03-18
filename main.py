import xml.dom.minidom
import requests
import re
import json
import os
import shutil
import html
import uuid
import email.utils
from datetime import datetime, timezone, timedelta
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import summarize
import report 
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def is_recent_pubdate(pubdate_str: str, days: int = 2) -> bool:
    """
    判断 pubDate 字符串是否在最近 N 天内
    
    Args:
        pubdate_str: RSS 中的 pubDate 字符串
        days: 近 N 天，默认为 2
    
    Returns:
        bool: True 表示在近 N 天内
    """
    if not pubdate_str:
        return False
    
    try:
        # 自动解析 RFC 2822 等常见日期格式（包括 GMT, +0000, +0800 等）
        parsed_dt = email.utils.parsedate_to_datetime(pubdate_str)
    except (ValueError, TypeError):
        # 解析失败，视为无效日期
        return False
    
    # 确保时间是带时区的（parsedate_to_datetime 会保留时区信息）
    if parsed_dt.tzinfo is None:
        # 如果没有时区，默认视为 UTC
        parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
    
    # 获取当前时间（带时区）
    now = datetime.now(timezone.utc)
    
    # 计算时间差
    diff = now - parsed_dt
    
    # 判断是否在指定天数内（注意：可能是未来时间，所以用 abs？但 RSS 一般不会发未来时间）
    # 更合理的做法：只考虑过去的时间
    return 0 <= diff.total_seconds() <= days * 24 * 3600


def safe_get_text(item, tag_name: str, default: str = "") -> str:
    """
    安全地从 DOM 元素中提取指定标签的文本内容。
    
    Args:
        item: DOM 元素节点
        tag_name: 要查找的标签名（如 'title', 'description'）
        default: 默认返回值（当标签不存在或无内容时）
    
    Returns:
        标签内的文本内容，或默认值
    """
    elements = item.getElementsByTagName(tag_name)
    if not elements:
        return default
    
    first_element = elements[0]
    if not first_element.firstChild:
        return default
        
    return first_element.firstChild.nodeValue.strip()

def extract_text_with_regex(description):
    """
    使用正则表达式移除HTML标签
    """
    # 提取CDATA中的内容
    cdata_pattern = r'<!\[CDATA\[(.*?)\]\]>'
    match = re.search(cdata_pattern, description, re.DOTALL)
    
    if match:
        html_content = match.group(1)
    else:
        html_content = description
    
    # 移除HTML标签
    clean_text = re.sub(r'<[^>]+>', ' ', html_content)
    clean_text = html.unescape(clean_text)
    # 移除CDATA标记（如果有残留）
    clean_text = clean_text.replace('&lt;', '<').replace('&gt;', '>')
    clean_text = clean_text.replace('&amp;', '&').replace('&quot;', '"')
    
    # 清理多余空格和换行
    clean_text = re.sub(r'\s+', ' ', clean_text)
    clean_text = clean_text.strip()
    
    return clean_text

import xml.etree.ElementTree as ET
from typing import Dict, List

def extract_groups_and_xmlurls(file_path: str) -> Dict[str, List[str]]:
    """
    从 OPML 文件中提取分组和对应的 xmlUrl 列表。

    Args:
        file_path (str): OPML 文件路径（如 'rss.txt'）

    Returns:
        Dict[str, List[str]]: 字典，key 为分组名，value 为 xmlUrl 列表
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 处理可能存在的 HTML 实体（如 &apos;），避免解析错误
        content = content.replace('&apos;', "'")

        root = ET.fromstring(content)
        body = root.find('body')
        if body is None:
            logging.warning(f"OPML 文件 {file_path} 中未找到 body 元素")
            return {}

        result = {}

        for outline in body.findall('outline'):
            group_name = outline.get('text')
            if not group_name:
                continue

            # 初始化该分组的列表
            urls = []

            # 遍历子 outline（即具体的 RSS 条目）
            for item in outline.findall('outline'):
                xml_url = item.get('xmlUrl')
                if xml_url:
                    urls.append(xml_url)

            # 只有当有有效 xmlUrl 时才加入结果
            if urls:
                result[group_name] = urls

        logging.info(f"成功解析 OPML 文件，共找到 {len(result)} 个分组")
        return result
    except ET.ParseError as e:
        logging.error(f"解析 OPML 文件失败 {file_path}: {e}")
        return {}
    except Exception as e:
        logging.error(f"读取 OPML 文件失败 {file_path}: {e}")
        return {}

def clean_xml_text(xml_text: str) -> str:
    """
    清理XML文本中的常见格式问题
    
    Args:
        xml_text (str): 原始XML文本
        
    Returns:
        str: 清理后的XML文本
    """
    import re
    
    # 修复HTML实体被误用为XML实体的问题
    text = xml_text
    text = text.replace('&#038;', '&amp;')  # 将错误的 &#038; 替换为正确的 &amp;
    text = text.replace('&amp;amp;', '&amp;')  # 修复双重转义
    
    # 查找可能有问题的单独 & 符号（不是HTML/XML实体的 &）
    problem_amp_pattern = r'&(?!(?:[a-zA-Z0-9#]{1,8};))'
    problematic_amps = list(re.finditer(problem_amp_pattern, text))
    if problematic_amps:
        # 修复单独出现的 & 符号
        text = re.sub(problem_amp_pattern, '&amp;', text)
    
    return text

def rss2json(url, group):
    headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,zh-TW;q=0.8,zh-HK;q=0.7,en-US;q=0.6,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    try:
        response = requests.get(url, timeout=20, headers=headers, allow_redirects=True,verify=False)
        response.raise_for_status()  # 如果状态码不是2xx，会抛出HTTPError
    except requests.RequestException as e:
        logging.error(f"请求失败 {url}: {e}")
        return

    try:
        text = response.content.decode('utf-8')
    except UnicodeDecodeError:
        # 如果UTF-8解码失败，尝试检测编码
        import chardet
        detected = chardet.detect(response.content)
        encoding = detected['encoding'] if detected['confidence'] > 0.7 else 'utf-8'
        logging.info(f"检测到编码: {encoding} (置信度: {detected.get('confidence', 0):.2f}) - {url}")
        try:
            text = response.content.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            # 如果检测失败，尝试常见编码
            for enc in ['gbk', 'gb2312', 'latin1', 'cp1252']:
                try:
                    text = response.content.decode(enc)
                    logging.info(f"使用编码 {enc} 成功解码 - {url}")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                logging.error(f"无法解码响应内容 - {url}")
                return
            
    clean_text = clean_xml_text(text)
    # print("cleaned xml text:", clean_text[:500])  # 打印前500字符以供调试
    try:
        dom = xml.dom.minidom.parseString(clean_text)
    except Exception as e:
        logging.error(f"XML解析失败 {url}: {e}")
        return

    root = dom.documentElement
    
    items = root.getElementsByTagName("item")

    xml_data = {}
    source = root.getElementsByTagName("title")[0]
    xml_data["source"] = source.firstChild.data
    xml_data["items"] = []
    count = 0
    for item in items:
        # title = item.getElementsByTagName("title")[0]
        # description = item.getElementsByTagName("description")[0]
        # link = item.getElementsByTagName("link")[0]
        # pubDate = item.getElementsByTagName("pubDate")[0]
        # print("title",":",title.firstChild.data)
        # print("description",":",extract_text_with_regex(description.firstChild.data))
        # print("link",":",link.firstChild.data)
        # print("pubDate",":",pubDate.firstChild.data)
        # print('-'*30)  # 添加空行分隔每个item
        pubDate = safe_get_text(item, "pubDate")
        if not is_recent_pubdate(pubDate, days=2):
            continue
        item_data = {
            "title": safe_get_text(item, "title"),
            "description": extract_text_with_regex(safe_get_text(item, "description")),
            "link": safe_get_text(item, "link"),
            #"pubDate": pubDate,
        }
        # print(item_data)
        xml_data["items"].append(item_data)
        count += 1
    
    logging.info(f"在 {url} 中找到 {count} 个近期条目")
    
    if len(xml_data["items"]) > 1:
        try:
            with open(os.path.join('rss_data', group, f'{uuid.uuid4()}.json'), 'w', encoding='utf-8') as f:
                json.dump(xml_data, f, ensure_ascii=False, indent=2)
            logging.info(f"成功保存 {len(xml_data['items'])} 个条目到 {group} 分组")
        except Exception as e:
            logging.error(f"保存文件失败 {group}: {e}")


def merge_json_files():
    """
    将每个分组对应的文件夹下的所有json文件合并成一个新的符合json格式的文件
    删去原先的json文件，仅仅保留合并后的文件，文件名就是分组名
    合并后的json放在rss_data文件夹中
    """
    logging.info("开始合并JSON文件")
    
    if not os.path.exists('rss_data'):
        logging.warning("rss_data目录不存在，跳过合并步骤")
        return
    
    for group in os.listdir('rss_data'):
        group_path = os.path.join('rss_data', group)
        
        # 检查是否是目录
        if not os.path.isdir(group_path):
            continue
            
        # 获取该分组目录下的所有json文件
        json_files = [f for f in os.listdir(group_path) if f.endswith('.json')]
        
        if not json_files:
            logging.info(f"分组 {group} 中没有JSON文件需要合并")
            continue
        
        logging.info(f"开始合并分组 {group} 的 {len(json_files)} 个JSON文件")
        
        # 合并所有JSON文件
        merged_data = {
            "source": f"{group}_merged",  # 使用分组名作为合并后的源名称
            "items": []
        }
        
        total_items = 0
        for json_file in json_files:
            json_file_path = os.path.join(group_path, json_file)
            try:
                with open(json_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # 如果数据格式是包含source和items的结构
                if 'items' in data and isinstance(data['items'], list):
                    merged_data["items"].extend(data["items"])
                    total_items += len(data["items"])
                    
                    # 更新source名称为原始RSS源的名称（如果有）
                    if 'source' in data and data['source'] != merged_data['source']:
                        if merged_data['source'] == f"{group}_merged":
                            merged_data['source'] = data['source']
                        else:
                            merged_data['source'] = f"{merged_data['source']}, {data['source']}"
                else:
                    # 如果格式不一致，尝试直接添加（兼容其他格式）
                    if isinstance(data, list):
                        merged_data["items"].extend(data)
                        total_items += len(data)
                        
            except json.JSONDecodeError as e:
                logging.error(f"JSON文件解析失败 {json_file_path}: {e}")
            except Exception as e:
                logging.error(f"读取文件失败 {json_file_path}: {e}")
        
        # 生成合并后的文件名（分组名 + .json），保存在rss_data根目录
        merged_file_path = os.path.join('rss_data', f'{group}.json')
        
        # 写入合并后的数据
        try:
            with open(merged_file_path, 'w', encoding='utf-8') as f:
                json.dump(merged_data, f, ensure_ascii=False, indent=2)
            logging.info(f"分组 {group} 合并完成，共 {total_items} 个条目，保存到 {merged_file_path}")
        except Exception as e:
            logging.error(f"保存合并文件失败 {merged_file_path}: {e}")
            continue
        
        # 删除原json文件
        for json_file in json_files:
            json_file_path = os.path.join(group_path, json_file)
            try:
                os.remove(json_file_path)
                logging.debug(f"删除原始文件: {json_file_path}")
            except Exception as e:
                logging.error(f"删除文件失败 {json_file_path}: {e}")
        
        # 删除空的分组目录
        try:
            os.rmdir(group_path)
            logging.debug(f"删除空的分组目录: {group_path}")
        except Exception as e:
            logging.error(f"删除分组目录失败 {group_path}: {e}")
        
        logging.info(f"分组 {group} 合并及清理完成")
    
    logging.info("JSON文件合并完成")


def truncate_json_files(max_context_length: int = 204000):
    """
    检查rss_data目录下的JSON文件长度，如果超过大模型上下文长度，
    则对最长的description进行摘要，直到文件长度小于上下文长度。
    如果对description摘要无法减少长度，则开始对title进行摘要
    如果对title摘要也无法减少长度，则开始删除最长的link
    如果无link可删去时，删除掉最长的item直到满足条件为止
    
    Args:
        max_context_length (int): 大模型上下文长度，默认204000
    """
    logging.info(f"开始检查JSON文件长度，最大上下文长度: {max_context_length}")
    
    if not os.path.exists('rss_data'):
        logging.warning("rss_data目录不存在，跳过文件长度检查")
        return
    
    # 获取rss_data目录下的所有json文件
    json_files = [f for f in os.listdir('rss_data') if f.endswith('.json')]
    
    if not json_files:
        logging.info("rss_data目录中没有JSON文件需要检查")
        return
    
    for json_file in json_files:
        json_file_path = os.path.join('rss_data', json_file)
        
        try:
            # 读取JSON文件
            with open(json_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 计算当前文件的文本长度（转换为字符串后的长度）
            current_content = json.dumps(data, ensure_ascii=False)
            current_length = len(current_content)
            
            logging.info(f"文件 {json_file} 当前长度: {current_length}")
            
            # 如果当前长度小于等于最大上下文长度，跳过
            if current_length <= max_context_length:
                logging.info(f"文件 {json_file} 长度正常，无需处理")
                continue
            
            # 循环处理，直到长度小于最大上下文长度
            iteration = 0
            # 用于追踪摘要长度是否在减少，如果连续多次未减少则切换到下一个处理策略
            prev_length = current_length
            no_reduction_count = 0
            processing_stage = "description"  # "description", "title", "link", "item"
            
            while current_length > max_context_length:
                iteration += 1
                logging.info(f"文件 {json_file} 长度超出限制，正在进行第 {iteration} 次处理，当前阶段: {processing_stage}")
                
                if processing_stage == "description":
                    # 查找最长的description
                    longest_desc_index = -1
                    max_desc_length = -1
                    
                    for i, item in enumerate(data.get('items', [])):
                        desc = item.get('description', '')
                        if len(desc) > max_desc_length:
                            max_desc_length = len(desc)
                            longest_desc_index = i
                    
                    # 如果没有找到有效的description，切换到title摘要
                    if longest_desc_index == -1 or max_desc_length <= 0:
                        logging.info(f"文件 {json_file} 中没有找到有效的description，切换到title摘要")
                        processing_stage = "title"
                        continue
                    
                    logging.info(f"第 {iteration} 次处理 - 最长description长度: {max_desc_length}，索引: {longest_desc_index}")
                    
                    # 对最长的description进行摘要
                    original_desc = data['items'][longest_desc_index]['description']
                    try:
                        summarized_desc = summarize.advanced_summarize_rss_description(original_desc)
                        data['items'][longest_desc_index]['description'] = summarized_desc
                        
                        logging.info(f"摘要前长度: {len(original_desc)}, 摘要后长度: {len(summarized_desc)}")
                        
                        # 检查长度是否减少
                        if len(original_desc) == len(summarized_desc):
                            no_reduction_count += 1
                            logging.info(f"摘要长度未减少，计数: {no_reduction_count}")
                        else:
                            no_reduction_count = 0  # 重置计数器
                            
                    except Exception as e:
                        logging.error(f"摘要处理失败 {json_file} 的描述: {e}")
                        break
                elif processing_stage == "title":
                    # 摘要title
                    longest_title_index = -1
                    max_title_length = -1
                    
                    for i, item in enumerate(data.get('items', [])):
                        title = item.get('title', '')
                        if len(title) > max_title_length:
                            max_title_length = len(title)
                            longest_title_index = i
                    
                    # 如果没有找到有效的title，切换到删除link
                    if longest_title_index == -1 or max_title_length <= 0:
                        logging.info(f"文件 {json_file} 中没有找到有效的title，切换到删除link")
                        processing_stage = "link"
                        continue
                    
                    logging.info(f"第 {iteration} 次处理 - 最长title长度: {max_title_length}，索引: {longest_title_index}")
                    
                    # 对最长的title进行摘要（使用description的摘要函数）
                    original_title = data['items'][longest_title_index]['title']
                    try:
                        # 使用summarize.advanced_summarize_rss_description来处理title
                        summarized_title = summarize.advanced_summarize_rss_description(original_title)
                        data['items'][longest_title_index]['title'] = summarized_title
                        
                        logging.info(f"标题摘要前长度: {len(original_title)}, 摘要后长度: {len(summarized_title)}")
                        
                        # 检查长度是否减少
                        if len(original_title) == len(summarized_title):
                            no_reduction_count += 1
                            logging.info(f"标题摘要长度未减少，计数: {no_reduction_count}")
                        else:
                            no_reduction_count = 0  # 重置计数器
                            
                    except Exception as e:
                        logging.error(f"标题摘要处理失败 {json_file}: {e}")
                        break
                elif processing_stage == "link":
                    # 删除最长的link
                    longest_link_index = -1
                    max_link_length = -1
                    
                    for i, item in enumerate(data.get('items', [])):
                        link = item.get('link', '')
                        if len(link) > max_link_length:
                            max_link_length = len(link)
                            longest_link_index = i
                    
                    # 如果没有找到有效的link，切换到删除item
                    if longest_link_index == -1 or max_link_length <= 0:
                        logging.info(f"文件 {json_file} 中没有有效的link可删除，切换到删除item")
                        processing_stage = "item"
                        continue
                    
                    logging.info(f"第 {iteration} 次处理 - 最长link长度: {max_link_length}，索引: {longest_link_index}")
                    
                    # 删除最长的link
                    original_link = data['items'][longest_link_index]['link']
                    data['items'][longest_link_index]['link'] = ""  # 清空link字段
                    
                    logging.info(f"删除链接: {original_link[:50]}...")
                    
                    # 长度减少计数器
                    no_reduction_count = 0  # 删除link通常有效，重置计数器
                else:  # processing_stage == "item"
                    # 删除最长的item（按总文本长度）
                    longest_item_index = -1
                    max_item_length = -1
                    
                    for i, item in enumerate(data.get('items', [])):
                        # 计算整个item的文本长度（title + description + link）
                        item_text = item.get('title', '') + item.get('description', '') + item.get('link', '')
                        item_length = len(item_text)
                        
                        if item_length > max_item_length:
                            max_item_length = item_length
                            longest_item_index = i
                    
                    # 如果没有有效的item可删除，跳出循环
                    if longest_item_index == -1 or max_item_length <= 0:
                        logging.warning(f"文件 {json_file} 中没有有效的item可删除，停止处理")
                        break
                    
                    logging.info(f"第 {iteration} 次处理 - 最长item长度: {max_item_length}，索引: {longest_item_index}")
                    
                    # 删除最长的item
                    removed_item = data['items'].pop(longest_item_index)
                    
                    logging.info(f"删除item: {removed_item.get('title', '')[:50]}...")
                    
                    # 长度减少计数器
                    no_reduction_count = 0  # 删除item通常有效，重置计数器
                
                # 重新计算文件长度
                current_content = json.dumps(data, ensure_ascii=False)
                current_length = len(current_content)
                
                logging.info(f"第 {iteration} 次处理后，文件 {json_file} 长度: {current_length}")
                
                # 检查长度是否在减少
                if current_length >= prev_length:
                    no_reduction_count += 1
                else:
                    no_reduction_count = 0
                    
                prev_length = current_length
                
                # 如果连续10次长度没有减少，切换到下一个处理阶段
                if no_reduction_count >= 10:
                    if processing_stage == "description":
                        logging.info(f"连续{no_reduction_count}次description摘要长度未减少，切换到title摘要")
                        processing_stage = "title"
                        no_reduction_count = 0  # 重置计数器
                    elif processing_stage == "title":
                        logging.info(f"连续{no_reduction_count}次title摘要长度未减少，切换到删除link")
                        processing_stage = "link"
                        no_reduction_count = 0  # 重置计数器
                    elif processing_stage == "link":
                        logging.info(f"连续{no_reduction_count}次删除link也未减少长度，切换到删除item")
                        processing_stage = "item"
                        no_reduction_count = 0  # 重置计数器
                    else:  # processing_stage == "item"
                        logging.warning(f"连续{no_reduction_count}次删除item也未减少长度，停止处理")
                        break
                
                # 添加安全检查，防止无限循环
                if iteration > 10000:  # 最多处理10000次
                    logging.warning(f"文件 {json_file} 处理次数超过限制，停止处理")
                    break
                
                # 检查是否还有items，如果没有则跳出
                if not data.get('items', []):
                    logging.warning(f"文件 {json_file} 中已无items，停止处理")
                    break
            
            # 保存处理后的文件
            try:
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logging.info(f"文件 {json_file} 处理完成，最终长度: {len(json.dumps(data, ensure_ascii=False))}")
            except Exception as e:
                logging.error(f"保存处理后的文件失败 {json_file_path}: {e}")
                
        except json.JSONDecodeError as e:
            logging.error(f"JSON文件解析失败 {json_file_path}: {e}")
        except Exception as e:
            logging.error(f"处理文件失败 {json_file_path}: {e}")
    
    logging.info("JSON文件长度检查和处理完成")



if __name__ == "__main__":
    logging.info("开始处理 RSS 订阅")
    
    groups = extract_groups_and_xmlurls('rss.txt')
    
    if os.path.exists('rss_data'):
        shutil.rmtree('rss_data')
        logging.info("清理旧的 rss_data 目录")
    if os.path.exists('generated_reports'):
        shutil.rmtree('generated_reports')
        logging.info("清理旧的 generated_reports 目录")
    if os.path.exists('daily_reports'):
        shutil.rmtree('daily_reports')
        logging.info("清理旧的 daily_reports 目录")
    
    os.makedirs('rss_data', exist_ok=True)
    logging.info("创建 rss_data 目录")
    
    total_urls = sum(len(urls) for urls in groups.values())
    logging.info(f"共找到 {len(groups)} 个分组，{total_urls} 个 RSS 地址")
    

    with ThreadPoolExecutor(max_workers=20) as executor:
        for group, urls in groups.items():
            group_dir = os.path.join('rss_data', group)
            os.makedirs(group_dir, exist_ok=True)
            
            # for i, url in enumerate(urls):
            #     logging.info(f"正在处理分组: {group}, URL {i+1}/{len(urls)}: {url}")
            #     rss2json(url, group)
            futures = [executor.submit(rss2json, url, group) for url in urls]
    logging.info("RSS 处理完成")

    merge_json_files()

    truncate_json_files()
    # 生成日报
    logging.info("\n开始生成日报...")
    report_files = report.generate_daily_report_prompt()
    
    # 发送邮件（优化后的合并发送）
    if report_files:
        logging.info("\n开始发送合并邮件...")
        report.send_combined_email_report(report_files)

    pass