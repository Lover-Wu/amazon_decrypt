"""
Amazon产品标题分析工具
分析产品标题中的关键词组、频率、位置和行文风格
"""

import json
import re
from collections import Counter, defaultdict
from typing import List, Dict, Tuple
import os
from dotenv import load_dotenv
from openai import OpenAI

# 加载环境变量
load_dotenv()


class TitleAnalyzer:
    """标题分析器"""
    
    def __init__(self, json_file_path: str):
        """
        初始化分析器
        
        Args:
            json_file_path: JSON数据文件路径
        """
        self.json_file_path = json_file_path
        self.titles = []
        self.products = []
        
        # 初始化Deepseek客户端
        api_key = os.getenv('DEEPSEEK_API_KEY')
        if api_key:
            self.client = OpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com"
            )
        else:
            print("警告: 未找到DEEPSEEK_API_KEY，AI分析功能将不可用")
            self.client = None
    
    def load_data(self) -> List[Dict]:
        """
        读取JSON文件
        
        Returns:
            产品列表
        """
        with open(self.json_file_path, 'r', encoding='utf-8') as f:
            self.products = json.load(f)
        
        # 提取所有标题（去重）
        seen_titles = set()
        for product in self.products:
            title = product.get('title', '')
            if title and title not in seen_titles:
                self.titles.append(title)
                seen_titles.add(title)
        
        print(f"已加载 {len(self.products)} 个产品记录")
        print(f"去重后共 {len(self.titles)} 个唯一标题")
        return self.products
    
    def extract_ngrams(self, text: str, n: int = 2) -> List[str]:
        """
        提取n-gram词组
        
        Args:
            text: 输入文本
            n: n-gram的大小
            
        Returns:
            词组列表
        """
        # 清理文本，移除特殊字符，保留字母数字和空格
        text = re.sub(r'[^\w\s]', ' ', text)
        words = text.lower().split()
        
        # 过滤停用词和短词
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
        words = [w for w in words if w not in stop_words and len(w) > 1]
        
        ngrams = []
        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i+n])
            ngrams.append(ngram)
        
        return ngrams
    
    def extract_all_ngrams(self, max_n: int = 4) -> Dict[int, List[str]]:
        """
        提取所有标题的1-gram到max_n-gram
        
        Args:
            max_n: 最大n-gram大小
            
        Returns:
            按n值分组的词组字典
        """
        all_ngrams = defaultdict(list)
        
        for title in self.titles:
            for n in range(1, max_n + 1):
                ngrams = self.extract_ngrams(title, n)
                all_ngrams[n].extend(ngrams)
        
        return all_ngrams
    
    def analyze_phrase_frequency(self, min_freq: int = 2) -> Dict[int, List[Tuple[str, int]]]:
        """
        分析词组频率
        
        Args:
            min_freq: 最小出现频率
            
        Returns:
            按n-gram大小分组的频率统计
        """
        all_ngrams = self.extract_all_ngrams(max_n=5)
        frequency_stats = {}
        
        for n, ngrams in all_ngrams.items():
            counter = Counter(ngrams)
            # 过滤掉低频词组
            frequent_phrases = [(phrase, count) for phrase, count in counter.most_common() 
                              if count >= min_freq]
            frequency_stats[n] = frequent_phrases
        
        return frequency_stats
    
    def analyze_phrase_positions(self) -> Dict[str, Dict[str, float]]:
        """
        分析词组在标题中的位置分布
        
        Returns:
            词组位置统计（平均位置、开头出现次数等）
        """
        phrase_positions = defaultdict(lambda: {'positions': [], 'at_start': 0, 'total': 0})
        
        for title in self.titles:
            # 分析2-gram和3-gram
            for n in [2, 3, 4]:
                ngrams = self.extract_ngrams(title, n)
                for idx, phrase in enumerate(ngrams):
                    phrase_positions[phrase]['positions'].append(idx)
                    phrase_positions[phrase]['total'] += 1
                    if idx == 0:
                        phrase_positions[phrase]['at_start'] += 1
        
        # 计算统计信息
        position_stats = {}
        for phrase, data in phrase_positions.items():
            if data['total'] >= 2:  # 至少出现2次
                avg_position = sum(data['positions']) / len(data['positions'])
                start_ratio = data['at_start'] / data['total']
                position_stats[phrase] = {
                    'avg_position': avg_position,
                    'start_ratio': start_ratio,
                    'total_count': data['total']
                }
        
        return position_stats
    
    def analyze_title_structure(self) -> Dict[str, any]:
        """
        分析标题结构特征
        
        Returns:
            标题结构统计
        """
        lengths = []
        word_counts = []
        has_brand = 0
        has_size = 0
        has_color = 0
        has_dash = 0
        
        for title in self.titles:
            lengths.append(len(title))
            word_counts.append(len(title.split()))
            
            # 检查常见元素
            if re.search(r'\b\d+\s*(inch|in|ft|cm|mm)\b', title.lower()):
                has_size += 1
            if re.search(r'\b(black|white|brown|gray|grey|wood|rustic)\b', title.lower()):
                has_color += 1
            if ' - ' in title:
                has_dash += 1
        
        total = len(self.titles)
        
        return {
            'avg_length': sum(lengths) / total if total > 0 else 0,
            'avg_word_count': sum(word_counts) / total if total > 0 else 0,
            'size_mention_ratio': has_size / total if total > 0 else 0,
            'color_mention_ratio': has_color / total if total > 0 else 0,
            'dash_usage_ratio': has_dash / total if total > 0 else 0,
            'total_titles': total
        }
    
    def analyze_with_ai(self, sample_titles: List[str] = None) -> str:
        """
        使用Deepseek AI分析标题风格
        
        Args:
            sample_titles: 样本标题列表，如果为None则使用所有标题
            
        Returns:
            AI分析结果
        """
        if not self.client:
            return "AI分析不可用：未配置API密钥"
        
        # 使用样本标题或全部标题
        titles_to_analyze = sample_titles if sample_titles else self.titles[:15]
        
        prompt = f"""请分析以下Amazon产品标题的行文风格和规律：

标题样本：
{chr(10).join([f"{i+1}. {title}" for i, title in enumerate(titles_to_analyze)])}

请从以下角度进行分析：
1. 标题的典型结构和格式
2. 常见的关键信息顺序（如尺寸、颜色、功能等的排列）
3. 用词特点和风格
4. 品牌名称的位置
5. 产品类型和用途的描述方式
6. 其他值得注意的规律

请用中文回答，提供具体的分析和建议。"""
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "你是一个专业的电商产品标题分析专家，擅长分析Amazon产品标题的规律和最佳实践。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"AI分析出错: {str(e)}"
    
    def generate_report(self, output_file: str = None) -> str:
        """
        生成完整的分析报告
        
        Args:
            output_file: 输出文件路径，如果为None则只返回字符串
            
        Returns:
            报告内容
        """
        print("正在生成分析报告...")
        
        # 1. 词组频率分析
        print("- 分析词组频率...")
        frequency_stats = self.analyze_phrase_frequency(min_freq=2)
        
        # 2. 位置分析
        print("- 分析词组位置...")
        position_stats = self.analyze_phrase_positions()
        
        # 3. 结构分析
        print("- 分析标题结构...")
        structure_stats = self.analyze_title_structure()
        
        # 4. AI风格分析
        print("- 使用AI分析行文风格...")
        ai_analysis = self.analyze_with_ai()
        
        # 生成报告
        report_lines = [
            "=" * 80,
            "Amazon产品标题分析报告",
            "=" * 80,
            "",
            f"数据源: {self.json_file_path}",
            f"分析时间: {self._get_current_time()}",
            f"标题数量: {len(self.titles)}",
            "",
            "=" * 80,
            "一、标题结构统计",
            "=" * 80,
            f"平均标题长度: {structure_stats['avg_length']:.1f} 个字符",
            f"平均单词数: {structure_stats['avg_word_count']:.1f} 个词",
            f"包含尺寸信息的比例: {structure_stats['size_mention_ratio']*100:.1f}%",
            f"包含颜色信息的比例: {structure_stats['color_mention_ratio']*100:.1f}%",
            f"使用破折号分隔的比例: {structure_stats['dash_usage_ratio']*100:.1f}%",
            "",
            "=" * 80,
            "二、高频关键词组分析",
            "=" * 80,
        ]
        
        # 展示不同长度的高频词组
        for n in [2, 3, 4]:
            if n in frequency_stats and frequency_stats[n]:
                report_lines.append(f"\n{n}-词组 (Top 20):")
                report_lines.append("-" * 60)
                for phrase, count in frequency_stats[n][:20]:
                    report_lines.append(f"  {phrase:<40} 出现 {count} 次")
        
        # 位置分析 - 找出最常出现在开头的词组
        report_lines.extend([
            "",
            "=" * 80,
            "三、词组位置分析",
            "=" * 80,
            "\n最常出现在标题开头的词组 (Top 15):",
            "-" * 60
        ])
        
        sorted_by_start = sorted(position_stats.items(), 
                                key=lambda x: (x[1]['start_ratio'], x[1]['total_count']), 
                                reverse=True)
        for phrase, stats in sorted_by_start[:15]:
            report_lines.append(
                f"  {phrase:<40} "
                f"开头出现率: {stats['start_ratio']*100:.1f}% "
                f"(共{stats['total_count']}次)"
            )
        
        # 平均位置靠前的词组
        report_lines.extend([
            "",
            "平均位置最靠前的词组 (Top 15):",
            "-" * 60
        ])
        
        sorted_by_position = sorted(position_stats.items(), 
                                   key=lambda x: (x[1]['avg_position'], -x[1]['total_count']))
        for phrase, stats in sorted_by_position[:15]:
            if stats['total_count'] >= 3:  # 至少出现3次
                report_lines.append(
                    f"  {phrase:<40} "
                    f"平均位置: {stats['avg_position']:.1f} "
                    f"(共{stats['total_count']}次)"
                )
        
        # AI分析
        report_lines.extend([
            "",
            "=" * 80,
            "四、AI深度分析 - 标题行文风格",
            "=" * 80,
            "",
            ai_analysis,
            "",
            "=" * 80,
            "五、总结建议",
            "=" * 80,
        ])
        
        # 生成建议
        top_2grams = [phrase for phrase, _ in frequency_stats.get(2, [])[:5]]
        top_3grams = [phrase for phrase, _ in frequency_stats.get(3, [])[:5]]
        
        report_lines.extend([
            "",
            "1. 高频核心关键词组:",
            f"   - 2词组: {', '.join(top_2grams[:5])}",
            f"   - 3词组: {', '.join(top_3grams[:5])}",
            "",
            "2. 标题结构建议:",
            f"   - 建议标题长度: {structure_stats['avg_length']:.0f}±20 字符",
            f"   - 建议单词数: {structure_stats['avg_word_count']:.0f}±3 个词",
            f"   - 尺寸信息建议包含率: {structure_stats['size_mention_ratio']*100:.0f}%",
            "",
            "3. 关键信息位置建议:",
            "   - 优先在标题开头放置: 尺寸、核心功能、产品类型",
            "   - 可在后半部分说明: 颜色、材质、用途场景",
            "",
            "=" * 80,
            "报告结束",
            "=" * 80
        ])
        
        report_content = '\n'.join(report_lines)
        
        # 保存到文件
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report_content)
            print(f"\n报告已保存到: {output_file}")
        
        return report_content
    
    @staticmethod
    def _get_current_time() -> str:
        """获取当前时间字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    """主函数"""
    # 设置文件路径
    json_file = r"e:\Program\Project\AmazonOperationsAIPlatform\InfoCrawler\amazonDetailInfo\amazon_products_1_to_20.json"
    output_file = r"e:\Program\Project\AmazonOperationsAIPlatform\InfoCrawler\dataAnalyze\title_analysis_report.txt"
    
    # 创建分析器
    analyzer = TitleAnalyzer(json_file)
    
    # 加载数据
    analyzer.load_data()
    
    # 生成报告
    report = analyzer.generate_report(output_file)
    
    # 打印报告
    print("\n" + report)


if __name__ == "__main__":
    main()
