import re
import math
from collections import Counter, defaultdict
import jieba  # 中文分词库，如果没有可以安装: pip install jieba
from typing import List, Dict

def calculate_sentence_scores(sentences: List[str], language: str = 'en') -> List[float]:
    """
    计算句子得分，用于摘要提取
    
    Args:
        sentences: 句子列表
        language: 语言类型 ('en' for English, 'zh' for Chinese)
    
    Returns:
        句子得分列表
    """
    # 分词
    def tokenize(text: str, lang: str) -> List[str]:
        if lang == 'zh':
            # 中文分词
            return list(jieba.cut(text))
        else:
            # 英文分词 - 简单按空格和标点分割
            words = re.findall(r'\b\w+\b', text.lower())
            return [word for word in words if len(word) > 2]  # 过滤短词
    
    # 获取所有词
    all_words = []
    sentence_words = []
    for sent in sentences:
        words = tokenize(sent, language)
        sentence_words.append(words)
        all_words.extend(words)
    
    # 计算词频
    word_freq = Counter(all_words)
    total_words = len(all_words)
    
    # 计算每个句子的得分
    sentence_scores = []
    for i, words in enumerate(sentence_words):
        if not words:
            sentence_scores.append(0)
            continue
            
        # 句子得分 = 重要词数量 / 句子长度
        score = 0
        for word in words:
            if word in word_freq:
                # 使用TF-IDF思想，频率高的词分值相对较低
                score += word_freq[word] / total_words
        
        # 调整得分（避免过长句子得分过高）
        normalized_score = score / max(len(words), 1)
        sentence_scores.append(normalized_score)
    
    return sentence_scores

def extractive_summarize(description: str, max_length: int = 100, language: str = 'en') -> str:
    """
    基于句子重要性提取的摘要算法
    
    Args:
        description: 输入的描述文本
        max_length: 摘要最大长度
        language: 语言类型 ('en' for English, 'zh' for Chinese)
    
    Returns:
        摘要文本
    """
    if not description:
        return ""
    
    # 按标点符号分割句子
    if language == 'zh':
        sentences = re.split(r'[。！？；\n]', description)
    else:
        sentences = re.split(r'[.!?;,\n]', description)
    
    # 清理句子
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
    
    if not sentences:
        return description[:max_length] if len(description) > max_length else description
    
    # 如果句子太少，直接返回
    if len(sentences) == 1:
        sentence = sentences[0]
        return sentence[:max_length] if len(sentence) > max_length else sentence
    
    # 计算句子得分
    sentence_scores = calculate_sentence_scores(sentences, language)
    
    # 按得分排序，选择得分最高的句子
    scored_sentences = list(zip(sentences, sentence_scores, range(len(sentences))))
    scored_sentences.sort(key=lambda x: x[1], reverse=True)
    
    # 选择句子，直到达到最大长度
    selected_sentences = []
    current_length = 0
    
    for sentence, score, original_index in scored_sentences:
        # 检查长度限制
        if current_length + len(sentence) <= max_length:
            selected_sentences.append((sentence, original_index))
            current_length += len(sentence) + 1  # +1 for space
        else:
            break
    
    # 按原文顺序排列选中的句子
    selected_sentences.sort(key=lambda x: x[1])
    result = ' '.join([s[0] for s in selected_sentences])
    
    # 确保不超过最大长度
    if len(result) > max_length:
        result = result[:max_length]
    
    return result.strip()

def simple_extractive_summarize(description: str, max_length: int = 400) -> str:
    """
    简化版摘要算法 - 如果没有jieba库，可以使用这个版本
    """
    if not description:
        return ""
    
    # 简单按句号分割
    sentences = re.split(r'[.!?。！？\n]', description)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
    
    if not sentences:
        return description[:max_length] if len(description) > max_length else description
    
    # 选择前几个句子，直到达到长度限制
    result = []
    current_length = 0
    
    for sentence in sentences:
        if current_length + len(sentence) <= max_length:
            result.append(sentence)
            current_length += len(sentence) + 1
        else:
            break
    
    summary = '. '.join(result)
    
    # 如果还是太长，直接截取
    if len(summary) > max_length:
        summary = summary[:max_length]
    
    return summary.strip()

def calculate_dynamic_max_length(text: str, language: str = 'en') -> int:
    """
    根据文本长度动态计算合适的max_length参数
    
    Args:
        text: 输入文本
        language: 语言类型 ('en' for English, 'zh' for Chinese)
    
    Returns:
        动态计算的max_length值
    """
    text_length = len(text)
    
    if language == 'zh':
        # 中文字符统计
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(re.sub(r'\s', '', text))
        
        # 如果中文字符比例较高，按照中文处理
        if total_chars > 0 and chinese_chars / total_chars > 0.3:
            # 中文文本的长度计算
            if text_length < 100:
                return min(100, text_length)  # 很短的文本，返回原文长度或100
            elif text_length < 300:
                return min(120, text_length)  # 短文本
            elif text_length < 600:
                return min(200, text_length)  # 中等长度文本
            elif text_length < 1200:
                return min(300, text_length)  # 长文本
            else:
                return min(400, text_length)  # 很长的文本
        else:
            # 英文或混合文本
            words = re.findall(r'\b\w+\b', text)
            word_count = len(words)
            
            if word_count < 20:
                return min(100, text_length)
            elif word_count < 50:
                return min(150, text_length)
            elif word_count < 100:
                return min(250, text_length)
            elif word_count < 200:
                return min(400, text_length)
            else:
                return min(500, text_length)
    else:
        # 英文文本
        words = re.findall(r'\b\w+\b', text)
        word_count = len(words)
        
        if word_count < 20:
            return min(100, text_length)
        elif word_count < 50:
            return min(150, text_length)
        elif word_count < 100:
            return min(250, text_length)
        elif word_count < 200:
            return min(400, text_length)
        else:
            return min(500, text_length)

def summarize_rss_description(description: str, max_length: int = None) -> str:
    """
    专门用于RSS描述的摘要函数，支持动态计算max_length
    
    Args:
        description: RSS描述文本
        max_length: 可选的最大长度，如果为None则自动计算
    
    Returns:
        摘要文本
    """
    if not description:
        return ""
    
    # 检测语言（简单判断）
    # 如果中文字符比例超过30%，认为是中文
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', description))
    total_chars = len(re.sub(r'\s', '', description))
    
    if total_chars > 0 and chinese_chars / total_chars > 0.3:
        language = 'zh'
    else:
        language = 'en'
    
    # 如果没有指定max_length，则动态计算
    if max_length is None:
        max_length = calculate_dynamic_max_length(description, language)
    
    # 检查是否需要摘要
    if len(description) <= max_length:
        return description.strip()
    
    # 根据描述长度调整策略
    if len(description) < 100:
        # 如果描述很短，直接返回
        return description.strip()
    elif len(description) < 200:
        # 中等长度，可以稍微详细一些
        return extractive_summarize(description, max_length=max_length, language=language)
    else:
        # 长描述，需要摘要
        return extractive_summarize(description, max_length=max_length, language=language)

def advanced_summarize_rss_description(description: str, 
                                    min_length: int = 50, 
                                    max_length: int = None, 
                                    compression_ratio: float = 0.3) -> str:
    """
    高级摘要函数，支持多种动态参数调整
    
    Args:
        description: RSS描述文本
        min_length: 最小摘要长度
        max_length: 最大摘要长度（如果为None则自动计算）
        compression_ratio: 压缩比例（摘要长度/原文长度），默认0.3
    
    Returns:
        摘要文本
    """
    if not description:
        return ""
    
    # 检测语言
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', description))
    total_chars = len(re.sub(r'\s', '', description))
    
    if total_chars > 0 and chinese_chars / total_chars > 0.3:
        language = 'zh'
    else:
        language = 'en'
    
    original_length = len(description)
    
    # 如果没有指定max_length，则动态计算
    if max_length is None:
        dynamic_max = calculate_dynamic_max_length(description, language)
        # 使用压缩比例和动态计算的长度中的较小值
        max_length = min(dynamic_max, max(100, int(original_length * compression_ratio)))
    
    # 确保长度在合理范围内
    max_length = max(min_length, min(max_length, original_length))
    
    # 如果原文长度已经小于等于最大长度，直接返回
    if original_length <= max_length:
        return description.strip()
    
    # 调用摘要函数
    return extractive_summarize(description, max_length=max_length, language=language)

# 测试用例
if __name__ == "__main__":
    test_descriptions = [
        """00 背景 随着大模型与智能体从对话向任务执行扩展，能力的封装、复用与编排成为关键问题。SKILLS 作为能力抽象机制，将推理逻辑、工具调用与执行流程封装为可复用的技能单元，使模型在执行复杂任务时实现稳定、一致且可管理的操作。即便在 MCP 等机制存在的情况下，SKILLS 仍不可替代，MCP负责模型对外部工具的调用管理，而SKILLS的核心是通过元工具驱动的渐进式、按需提示词注入机制，实现低常驻上下文开销下的瞬时专家级能力加载。随着生态的快速发展，SKILLS 的数量与复杂度呈现爆发式增长，显示出其在自动化流程和能力管理中的核心价值。 100k+的SKILLS数量与指数级增长速度 SKILLS 最初由 Claude 团队在 Claude Code 中以私有形式开发，旨在扩展模型能力与任务逻辑；随着大模型生态的持续演进，它逐步从平台内部应用拓展至更广泛的 AI IDE 与自动化工作流场景。如今，SKILLS 的数量已超过 10 万，且仍保持指数级增长。能力封装不仅提升执行效率，也形成新的安全边界，对权限管理与执行控制提出挑战。SKILLS 已成为能力复用、任务执行与安全管理的核心模块，其潜在攻击面和生态价值值得系统关注。 本文将从架构设计、攻击实践、生态现状三个层面，深入剖析SKILLS安全攻击面的构成与潜在威胁，为相关方提供系统性的安全参考。 01 SKILLS攻击面分析，核心架构中隐藏的天然风险 SKILLS架构剖析 在Agent Skills的架构中，每个SKILL以文件系统上的独立目录形式存在。根目录下的SKILL.md文件是技能的说明书，通过前置元数据定义技能的功能描述与适用场景。这个文件不仅是静态元数据的载体，更包含完整的技能指令集，包括分步骤的操作指南、输入输出示例及案例说明，形成可被智能体直接解析的任务剧本。 当SKILL被激活时，智能体会优先加载SKILL.md的前置元数据完成快速校验，随后将整个指令正文载入上下文环境。scripts子目录中的脚本文件承接具体操作执行，通过API与外部系统交互。位于references目录的技术文档和assets目录的数据文件则构成技能的\"知识仓库\"，提供深度技术细节及静态资源；两者均采用按需加载机制，仅在需要时被调取，有效平衡了上下文内存占用与功能性需求。 SKILLS攻击面分析 在SKILL技术快速落地的背景下，其架构依托"提示词 + 可执行脚本"的组合来提升灵活性与操作规范性，但设计阶段缺乏统一、规范且包含安全验证的分发渠道，也未系统性地融入安全防护机制。这导致风险传导的起点往往位于供应链的薄弱环节：攻击者可通过依赖混淆、托管平台攻击或开发工具代码库入侵等手段对 SKILLS 进行投毒污染，将恶意成分植入可被系统加载的外部资源。由于 SKILLS 在运行时会将提示词用于模型上下文构建并影响推理行为，同时将脚本直接送入本地执行环境运行，这两类核心输入便成为风险进入系统的直接门户，一旦被污染即在系统内部被激活。 SKILLS攻击面及风险路径 正因如此，该架构在面对传统资源投毒攻击时尤为脆弱。其运行机制高度依赖文件加载与上下文注入，攻击者只需污染源头资源文件，即可在不直接接触运行环境的情况下实现影响扩散。尤其是当脚本通过本地代码执行器直接启动时，风险隐蔽性更强，大多数开发者与普通使用者依然难以在运行前及时察觉并阻断这类深层威胁。 "提示词"与"脚本"两类核心输入在遭受供应链污染后，会在不同环节触发连锁反应。提示词作为模型推理的关键组成部分，被篡改后会扰乱模型决策路径，造成内容生成偏差、输出违背预期甚至引导模型执行不安全指令，从而引发内容安全风险与提示词安全风险，还可能导致智能体在业务场景中输出违规或误导性信息；另一方面，脚本作为直接在本机执行的逻辑载体，若直接植入恶意代码或通过恶意包引入等更隐蔽的方式植入，便可能在执行时突破权限边界，触发未授权系统命令执行，导致系统破坏、敏感数据泄露等端侧风险，甚至使攻击者获得持久化控制。 代码相关风险与提示词风险在传播路径上相互叠加：前者作用于智能体的认知与生成层，后者直击系统执行层，使单一隐患在运行过程中被成倍放大。 02 SKILLS攻击面实战案例剖析 案例一：在SKILL脚本中植入代码，实现任意命令执行 利用Claude Code中skill-creator插件尝试创建一个命令执行环境演示上述的安全风险问题，例如创建一个用户日常最爱询问的话语，"今天天气怎么样"，当询问天气情况的时候调用skill查询api返回当前区域的天气情况，以下是生成好的SKILL.md 在weather.py脚本中增加命令执行"弹出计算器"的代码片段 在Opencode中加载恶意的SKILLS,当询问天气怎样，调用skill，触发执行逻辑触发命令执行。 案例二：SKILL创建器默认生成脚本存在危险函数 使用人工智能生成代码时，如未经过严格的安全审计，其产生漏洞的风险较高。当前大模型技术处于快速发展阶段，众多开源社区的开发者在利用此类工具生成代码时，往往忽视了对代码进行系统的安全性审查，导致仅依赖大模型生成的代码存在显著安全隐患。以使用 skill-creator 开发一个简单的四则运算 Skill 为例，若输入以下提示词： "使用 skill-creator 编写一个用于实现加减乘除计算的新 Skill"，skill-creator在领会用途后开始进行代码编写，采用python脚本实现具体功能： 可以看到大模型在编写代码的过程中就采用eval进行计算，虽然大模型有意识的使用了re模块过滤了空格进行防护，但实际仍存在安全风险，我们可以直接使用payload进行恶意代码执行： 03 SKILLS生态调研：快速增长，安全性待完善 SKILLS生态目前正处于快速发展阶段。据不完全统计，相关项目已超过105000个，覆盖了多样化的应用场景。与此同时，该生态已衍生出多个SKILLS市场，例如skill.sh市场，通过为SKILLS提供排名机制，帮助用户筛选出高效、高价值的SKILLS，提升了选择的便利性与有效性。 再例如skillstore.io等市场中增设安全性指标模块，对上线的SKILL进行统一的安全检测与质量评分。通过明确的评估结果向用户传递安全信任，帮助其更放心地选用经过审核的SKILL，从而提升整体生态的安全性与可靠性。 针对开源SKILLS安全性的采样研究与分析 天元实验室大模型安全团队在SKILL商店中采样了将近700个SKILL，在分析过程中我们采取了AI辅助分析的手段，通过OpenCode+提示词的方式快速的对这些SKILLS项目从静态扫描、动态分析和依赖审计这三个安全维度进行检测，目前暂未发现在野投毒事件，但静态扫描发现传统代码安全问题依然存在，也存在一些和案例相一致的风险。 针对开源SKILLS的AI分析报告 AI辅助分析的结果通过以下三个可视化图表呈现：饼图展示了技能目录安全审计报告中风险按严重程度的分布——8个严重风险占比约21.1%，需立即处置；中等与低风险各15个，均占约39.5%，前者多因配置不当或缺乏验证，后者多为教育性质内容或误报。 开源SKILLS安全性抽样分析统计 进一步结合按风险类别统计可见，代码执行类风险数量最高（20个），主要源于脚本中 shell=True 等不安全命令调用或包安装隐患；其次是文档类（18个），多为提及exploit、payload等敏感关键词的教育或误报场景；输入验证（11个）、文件操作（10个）、网络安全（8个）及密码学（5个）类风险依次递减，分别涉及用户输入未过滤、不安全解压或权限设置、代理/端口配置问题及弱加密或硬编码凭证等问题。 从受影响项目类型观察：安全工具类项目安全风险影响最大（22个），这与安全工具本身需高权限操作的特性直接相关；教育内容类紧随其后（18个），涵盖红队/蓝队演练教学材料；其余如数据库客户端、浏览器自动化等项目受影响相对较少。 分析表明，绝大多数"风险"集中于安全工具与教育内容类别，这些风险更多源自工具的研究属性与安全教学场景需求，而非恶意攻击意图。 如何应对SKILLS生态中的安全挑战 伴随SKILL快速发展，相应的安全问题尚未得到系统性解决。基于SKILLS生态的现状，我们仍需重点应对以下三个核心安全性挑战，并提供相应方案： 如何确保SKILL来源安全：下载SKILL时必须认准官方渠道，如官方GitHub等。开发人员与普通用户在下载过程中极易遭遇安全风险，常见攻击方式包括在GitHub、第三方下载市场等进行依赖投毒。目前SKILL已出现若干分发市场，例如skills.rest、skillsmp.com等，用户应优先通过官方认证渠道获取。 如何保障Agent执行环境安全：必须为Agent运行环境配置高强度的沙箱隔离机制，以避免恶意命令执行、越权操作等安全风险，确保执行过程受控且安全。 进行Agent上线前的安全扫描 在Agent上线前，应对其加载的SKILL进行系统化的安全检测，包括：①静态扫描：检测危险函数、敏感代码模式等；②动态分析：借助大语言模型（LLM）进行语义分析，识别潜在提示词注入等逻辑风险；③依赖审计：对代码脚本调用的第三方库进行人工或自动化校验，避免引入含有漏洞或被篡改的依赖包。 通过上述多维度的安全检查，可显著降低SKILL在客户端侧部署后的安全风险。 04 总结 SKILLS生态在自动化流程中扮演着日益关键的角色，其高速增长与核心价值正吸引着更多应用。然而，这种繁荣景象之下，复杂的安全挑战也悄然浮现。架构中的天然设计隐患、实践中被利用的攻击面，以及生态中尚未弥合的防护缺口，共同构成了一个亟待审视的安全战场。 本文首次对快速发展、备受关注的SKILLS生态进行了系统性技术架构与风险梳理，通过第一时间的实地抽样调研与实验分析，我们实证了相关攻击面真实存在，并对现网SKILLS应用现状与演变趋势进行了研判。鉴于大量SKILLS部署已涉及敏感业务数据，尤其建议予以高度警惕，将SKILLS纳入安全审计范畴，并强化安全评估与验证，以切实防范潜在风险。 绿盟科技天元实验室 专注于新型实战化攻防对抗技术研究。 研究目标包括：漏洞利用技术、防御绕过技术、攻击隐匿技术、攻击持久化技术等蓝军技术，以及攻击技战术、攻击框架的研究。涵盖Web安全、终端安全、AD安全、云安全等多个技术领域的攻击技术研究，以及工业互联网、车联网等业务场景的攻击技术研究。通过研究攻击对抗技术，从攻击视角提供识别风险的方法和手段，为威胁对抗提供决策支撑。 M01N Team公众号 聚焦高级攻防对抗热点技术 绿盟科技蓝军技术研究战队 官方攻防交流群 网络安全一手资讯 攻防技术答疑解惑 扫码加好友即可拉群 平台地址： http://www.jintiankansha.me/t/rAY5t51Xky"""  # 长文本
    ]
    
    for i, test_description in enumerate(test_descriptions):
        # 使用高级函数
        result2 = advanced_summarize_rss_description(test_description)
        print(f"高级动态计算摘要: {result2}")
        print(f"摘要长度: {len(result2)}")
        
        print("-" * 80)
