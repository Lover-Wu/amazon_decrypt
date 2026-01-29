import pandas as pd
import numpy as np
import jieba
import re
import warnings
import json
from dotenv import load_dotenv
from openai import OpenAI
import os
from typing import List, Dict, Union

# 机器学习/算法相关
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer
from gensim import corpora, models
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from mlxtend.frequent_patterns import apriori, association_rules
from snownlp import SnowNLP

# 全局配置
warnings.filterwarnings('ignore')
load_dotenv()  # 加载.env文件

# ===================== 1. 可拓展配置 =====================
# JSON文件路径（仅需配置这个）
JSON_FILE_PATH = "amazo_相机.json"

# 全局变量（动态赋值）
CATEGORY_NAME = ""
SIMULATE_FIELDS = {
    "category": "",
    "review": {}
}


def init_deepseek_client() -> OpenAI:
    """初始化DeepSeek客户端（复用并优化）"""
    api_key = os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        raise ValueError("错误：未找到DEEPSEEK_API_KEY，请在.env文件中配置")

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com"
    )
    return client


def extract_category_by_ai(client: OpenAI, product_titles: List[str]) -> str:
    """AI识别商品核心品类（强制仅返回一个核心品类）"""
    if not product_titles:
        raise ValueError("无商品标题数据，无法识别品类")

    # 采样前20个标题（避免token过多）
    sample_titles = product_titles[:20]
    # 重构提示词：强化"仅返回一个核心品类"的严格约束
    prompt = f"""
    请从以下亚马逊商品标题中识别**唯一的核心品类名称**，严格遵守以下要求：
    1. 必须仅返回**一个**核心品类名称，绝对禁止返回多个品类
    2. 只返回品类名本身，不要有任何解释、说明、标点、序号或多余文字
    3. 品类名格式参考：无线耳机、充电宝、智能手表、保温杯、数码相机（仅中文，2-6字）

    商品标题列表：
    {sample_titles}
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,  # 降低随机性，提升结果稳定性
            max_tokens=50
        )
        category = response.choices[0].message.content.strip()
        # 兜底处理：过滤所有非中文字符，确保仅保留核心品类名
        category = re.sub(r'[^\u4e00-\u9fa5]', '', category).strip()
        # 二次兜底：若仍为空或过长，默认取第一个合理品类
        if not category or len(category) > 10:
            category = "数码相机"
        print(f"AI识别核心品类：{category}")
        return category
    except Exception as e:
        raise Exception(f"AI识别品类失败：{str(e)}")


def extract_product_keywords_by_ai(client: OpenAI, title: str, category: str) -> List[str]:
    """AI提取单个商品标题的精准关键词（适配品类）"""
    if not title:
        return []

    prompt = f"""
    请提取以下{category}商品标题的核心关键词（仅返回中文关键词列表，用逗号分隔，每个关键词长度2-4字）：
    标题：{title}
    要求：1. 关键词需适配{category}品类特性 2. 排除无意义的介词/助词 3. 优先提取功能/属性/卖点
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=100
        )
        keywords = [kw.strip() for kw in response.choices[0].message.content.strip().split(",") if kw.strip()]
        return keywords
    except Exception as e:
        print(f"警告：AI提取[{title}]关键词失败，使用分词兜底：{e}")
        # 兜底：使用jieba分词
        stop_words = ['的', '适用', '专用', '款', '型', '为', '了', '适用于', 'for', 'with']
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', title)
        words = jieba.lcut(text)
        return [w for w in words if w not in stop_words and len(w) > 1]


def extract_batch_product_keywords_by_ai(
        client: OpenAI,
        titles: List[str],
        category: str,
        batch_size: int = 50  # 每批处理的标题数（可根据AI Token限制调整）
) -> List[List[str]]:
    """
    批量提取大量同品类标题的关键词（优化效率+成本）
    :param client: OpenAI客户端实例
    :param titles: 待处理的标题列表（大量）
    :param category: 统一的品类名称
    :param batch_size: 每批调用AI的标题数（默认50）
    :return: 与标题列表一一对应的关键词列表（每个元素是单个标题的关键词列表）
    """
    # 最终结果列表（与输入titles一一对应）
    all_keywords = []

    # 步骤1：过滤空标题，记录空标题位置（保证结果与输入顺序一致）
    valid_titles = []
    empty_title_indices = []
    for idx, title in enumerate(titles):
        if not title:
            empty_title_indices.append(idx)
            all_keywords.append([])  # 空标题直接返回空列表
        else:
            valid_titles.append((idx, title))  # 保留有效标题的原索引和内容

    if not valid_titles:
        return all_keywords  # 全是空标题，直接返回

    # 步骤2：分批次处理有效标题（避免单次Token过多）
    for i in range(0, len(valid_titles), batch_size):
        batch = valid_titles[i:i + batch_size]
        batch_indices = [item[0] for item in batch]  # 这批标题的原索引
        batch_titles = [item[1] for item in batch]  # 这批标题的内容

        # 构建批量处理的Prompt（核心：让AI返回结构化结果，方便拆分）
        prompt = f"""
        请批量提取以下{category}品类商品标题的核心关键词，严格遵守要求：
        1. 每个标题的关键词仅返回中文，用逗号分隔，每个关键词长度2-4字
        2. 关键词需适配{category}品类特性，排除无意义的介词/助词，优先提取功能/属性/卖点
        3. 按标题顺序返回，每个标题的关键词用【===】分隔，仅返回关键词，无其他多余文字

        商品标题列表（按顺序）：
        {chr(10).join([f"{idx + 1}. {title}" for idx, title in enumerate(batch_titles)])}
        """

        try:
            # 批量调用AI（一次请求处理一批标题，大幅减少调用次数）
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2000  # 批量处理需增大Token限制（根据batch_size调整）
            )

            # 解析AI返回的批量结果
            ai_result = response.choices[0].message.content.strip()
            # 按【===】拆分每个标题的关键词（与批量标题顺序一致）
            batch_keywords_str = [kw_str.strip() for kw_str in ai_result.split("===") if kw_str.strip()]

            # 处理AI返回结果（保证数量匹配）
            for j, idx in enumerate(batch_indices):
                if j < len(batch_keywords_str):
                    # 清洗单个标题的关键词
                    keywords = [kw.strip() for kw in batch_keywords_str[j].split(",") if kw.strip()]
                else:
                    # AI返回结果数量不匹配，兜底调用单标题函数
                    keywords = extract_product_keywords_by_ai(client, batch_titles[j], category)
                # 将结果放入原索引位置
                all_keywords.insert(idx, keywords)

        except Exception as e:
            # 批量AI调用失败，对这批标题逐个走原单标题逻辑（AI+分词兜底）
            print(f"警告：批量AI调用失败（批次{i // batch_size + 1}），降级为逐个处理：{e}")
            for j, idx in enumerate(batch_indices):
                keywords = extract_product_keywords_by_ai(client, batch_titles[j], category)
                all_keywords.insert(idx, keywords)

    return all_keywords


def batch_title_keywords_extractor(
        input_titles: List[str],
        batch_size: int = 50,
        save_result: bool = True,
        save_path: str = "./batch_keywords_result.json"
) -> Dict[str, List[str]]:
    """
    独立入口：输入批量标题，直接生成对应关键词（无需依赖JSON文件）
    :param input_titles: 批量商品标题列表
    :param batch_size: 每批处理的标题数
    :param save_result: 是否保存结果到JSON文件
    :param save_path: 结果保存路径
    :return: 字典{标题: 关键词列表}
    """
    print("===== 开始批量标题关键词提取 =====")
    # 1. 初始化AI客户端
    try:
        client = init_deepseek_client()
        print(" DeepSeek客户端初始化成功")
    except Exception as e:
        print(f" 客户端初始化失败：{e}")
        return {}

    # 2. AI识别核心品类
    try:
        category = extract_category_by_ai(client, input_titles)
        print(f"✅ 核心品类识别完成：{category}")
    except Exception as e:
        print(f"品类识别失败：{e}，使用默认品类'未识别品类'")
        category = "未识别品类"

    # 3. 批量提取关键词
    try:
        all_keywords = extract_batch_product_keywords_by_ai(client, input_titles, category, batch_size)
        print(f" 批量关键词提取完成，共处理{len(input_titles)}个标题")
    except Exception as e:
        print(f" 批量提取失败：{e}，降级为逐个提取")
        all_keywords = [extract_product_keywords_by_ai(client, title, category) for title in input_titles]

    # 4. 构建结果字典（标题: 关键词）
    result_dict = {title: keywords for title, keywords in zip(input_titles, all_keywords)}

    # 5. 保存结果（可选）
    if save_result:
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(result_dict, f, ensure_ascii=False, indent=4)
            print(f" 结果已保存到：{save_path}")
        except Exception as e:
            print(f" 结果保存失败：{e}")

    # 6. 打印部分结果示例
    print("\n===== 关键词提取结果示例（前5条） =====")
    sample_count = min(5, len(result_dict))
    for idx, (title, keywords) in enumerate(list(result_dict.items())[:sample_count], 1):
        print(f"{idx}. 标题：{title[:50]}..." if len(title) > 50 else f"{idx}. 标题：{title}")
        print(f"   关键词：{keywords}")
        print("-" * 80)

    return result_dict


def generate_dynamic_review_template(client: OpenAI, category: str) -> Dict[str, str]:
    """AI生成适配品类的评价模板（优化JSON解析容错）"""
    # 强化提示词：强制仅返回纯JSON，无任何多余文字
    prompt = f"""
    请为{category}品类生成6条评价（3条正面，3条负面），严格遵守以下要求：
    1. 仅返回JSON格式内容，不要添加任何额外文字、说明、注释、标点或换行
    2. JSON格式示例：{{"卖点1": "评价内容1", "卖点2": "评价内容2"}}
    3. 评价需贴合{category}的核心卖点/痛点，内容简洁真实（每条10-20字）
       ### 参考示例（数码相机品类） ###
        "画质清晰": "4K画质清晰，色彩还原度高",
        "操作简单": "操作便捷，新手也能快速上手",
        "防抖效果好": "防抖效果佳，视频拍摄不模糊",
        "画质差": "像素低，画质模糊不清晰",
        "操作复杂": "功能繁琐，新手难以操作",
        "续航短": "电池续航短，拍摄易断电"
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,  # 降低随机性，提升格式合规率
            max_tokens=300,
            response_format={"type": "json_object"}  # 强制JSON格式返回
        )
        ai_content = response.choices[0].message.content.strip()

        # 关键优化：提取JSON内容（即使AI返回多余文字，也能精准提取大括号内的JSON）
        json_match = re.search(r'\{[\s\S]*\}', ai_content, re.DOTALL)
        if json_match:
            ai_content = json_match.group()  # 只保留大括号包裹的JSON部分
        else:
            raise ValueError("未提取到有效JSON内容")

        # 解析JSON
        review_dict = json.loads(ai_content)
        # 校验JSON格式（确保是{k:v}结构，且数量符合要求）
        if not isinstance(review_dict, dict) or len(review_dict) != 6:
            raise ValueError(
                f"JSON格式不符合要求（需6条评价），当前长度：{len(review_dict) if isinstance(review_dict, dict) else '非字典'}")

        print(f"AI生成{category}评价模板：{review_dict}")
        return review_dict
    except Exception as e:
        print(f"警告：AI生成评价模板失败（{e}）")
        # 兜底默认模板（适配数码相机品类）
        return {
            "性价比高": f"{category}价格实惠，使用体验好",
            "续航长": f"{category}续航时间久，满足日常使用",
            "质量好": f"{category}做工精细，耐用性强",
            "续航短": f"{category}续航拉胯，频繁充电",
            "质量差": f"{category}做工粗糙，容易损坏",
            "价格高": f"{category}价格偏高，性价比低"
        }


# ===================== 2. JSON数据读取与空值处理 =====================
def read_amazon_json(file_path: str) -> Dict:
    """读取亚马逊JSON文件，处理文件读取异常 + 适配无total_products的JSON结构"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            json_str = f.read().strip()
            # 修复JSON格式不完整的问题（兜底）
            if not json_str.endswith("]") and not json_str.endswith("}"):
                # 适配数组格式的JSON
                if json_str.startswith("[") and not json_str.endswith("]"):
                    json_str += "]"
                elif json_str.count("{") > json_str.count("}"):
                    json_str += "}" * (json_str.count("{") - json_str.count("}"))
            data = json.loads(json_str)

        # 适配JSON结构：纯商品数组/单个商品对象/标准结构
        if isinstance(data, list):
            return {
                "total_products": len(data),
                "products": data
            }
        elif isinstance(data, dict) and "asin" in data and "title" in data and "total_products" not in data:
            return {
                "total_products": 1,
                "products": [data]
            }
        else:
            return data
    except FileNotFoundError:
        raise FileNotFoundError(f"未找到JSON文件：{file_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON解析失败：{e}，请检查文件完整性")


def clean_empty_fields(raw_data: Dict) -> List[Dict]:
    """清洗商品数据：过滤空值字段"""
    cleaned_products = []
    for product in raw_data.get("products", []):
        if not isinstance(product, dict):
            print(f"警告：跳过非字典格式商品数据：{product}")
            continue
        cleaned_product = {
            k: v for k, v in product.items()
            if v not in (None, "", [], {})
        }
        cleaned_products.append(cleaned_product)
    print(f"JSON数据清洗完成：原始{raw_data.get('total_products', 0)}条 → 有效{len(cleaned_products)}条")
    return cleaned_products


def extract_numeric_value(text: str) -> Union[float, None]:
    """提取字符串中的数值（支持$、千分位逗号）"""
    if not isinstance(text, str):
        return None
    # 移除所有货币符号和千分位逗号
    cleaned_text = text.replace("$", "").replace("S$", "").replace("¥", "").replace("元", "").replace(",", "")
    # 匹配带小数的数值
    nums = re.findall(r'(\d*[.]?\d+)', cleaned_text)
    if not nums:
        return None
    num_str = nums[-1]
    try:
        return float(num_str)
    except ValueError:
        return None


def extract_sales_from_purchase_hint(hint: str) -> int:
    """从purchase_hint提取销量数值（如1k+ →1000，500+→500，6k+→6000）"""
    if not isinstance(hint, str):
        return 0

    # 匹配数字+单位（k代表千）
    pattern = r'(\d+)k\+'
    match = re.search(pattern, hint.lower())
    if match:
        return int(match.group(1)) * 1000

    # 匹配纯数字+
    pattern = r'(\d+)\+'
    match = re.search(pattern, hint)
    if match:
        return int(match.group(1))

    return 0


def json_to_dataframe(cleaned_products: List[Dict], client: OpenAI) -> pd.DataFrame:
    """将清洗后的JSON数据转换为DataFrame（核心：真实销量/评论数替代）"""
    # 1. 提取所有标题，AI识别品类
    all_titles = [product.get("title", "") for product in cleaned_products if product.get("title")]
    global CATEGORY_NAME, SIMULATE_FIELDS
    CATEGORY_NAME = extract_category_by_ai(client, all_titles)
    SIMULATE_FIELDS["category"] = f"{CATEGORY_NAME}>{CATEGORY_NAME}"
    SIMULATE_FIELDS["review"] = generate_dynamic_review_template(client, CATEGORY_NAME)

    # 2. 构建DataFrame数据（新增JSON中有效字段）
    df_data = {
        "asin": [], "product_id": [], "title": [], "url": [],
        "price": [], "original_price": [], "discount_percentage": [],
        "category": [], "sales": [], "review": [], "ai_keywords": [],
        "reviews_count": [], "rating": [], "amazon_choice": [],
        "best_seller": [], "prime_eligible": [], "brand": [],
        "purchase_hint": []
    }

    np.random.seed(42)
    product_titles = [product.get("title", "") for product in cleaned_products]
    # 批量提取关键词
    batch_keywords = extract_batch_product_keywords_by_ai(client, product_titles, CATEGORY_NAME)

    for idx, product in enumerate(cleaned_products):
        # 核心字段填充
        df_data["asin"].append(product.get("asin", ""))
        df_data["product_id"].append(product.get("product_id", ""))
        title = product.get("title", "")
        df_data["title"].append(title)
        df_data["url"].append(product.get("url", ""))

        # 价格提取（强化容错）
        price = extract_numeric_value(product.get("price", ""))
        df_data["price"].append(price if price is not None else 0.0)

        # 原价/折扣处理
        original_price = extract_numeric_value(product.get("original_price", ""))
        df_data["original_price"].append(
            original_price if original_price is not None else price if price is not None else 0.0)

        # 计算折扣率
        if price and original_price and original_price > price:
            discount = ((original_price - price) / original_price) * 100
        else:
            discount = 0.0
        df_data["discount_percentage"].append(round(discount, 2))

        df_data["category"].append(SIMULATE_FIELDS["category"])

        # 核心修改：优先从purchase_hint提取真实销量，无则用评论数替代
        purchase_hint = product.get("purchase_hint", "")
        real_sales = extract_sales_from_purchase_hint(purchase_hint)
        if real_sales == 0:
            # 无真实销量则用评论数替代
            review_count = extract_numeric_value(product.get("reviews", ""))
            real_sales = int(review_count) if review_count is not None else 0
        df_data["sales"].append(real_sales)

        # 批量关键词赋值
        df_data["ai_keywords"].append(batch_keywords[idx])

        # 提取评论数字段
        reviews_count = extract_numeric_value(product.get("reviews", ""))
        df_data["reviews_count"].append(reviews_count if reviews_count is not None else 0)

        # 提取评分字段
        rating = extract_numeric_value(product.get("rating", ""))
        df_data["rating"].append(rating if rating is not None else 0.0)

        # 亚马逊特色标签
        df_data["amazon_choice"].append(1 if product.get("amazon_choice") else 0)
        df_data["best_seller"].append(1 if product.get("best_seller") else 0)
        df_data["prime_eligible"].append(1 if product.get("prime_eligible") else 0)

        # 品牌字段
        df_data["brand"].append(product.get("brand", ""))
        df_data["purchase_hint"].append(purchase_hint)

        # 基于AI关键词匹配评价
        review = "使用体验良好"
        title_lower = title.lower()
        for keyword, r in SIMULATE_FIELDS["review"].items():
            if keyword in title_lower or any(kw in title_lower for kw in batch_keywords[idx]):
                review = r
                break
        df_data["review"].append(review)

    # 转换为DataFrame并清洗
    df = pd.DataFrame(df_data)
    # 过滤空价格/空标题数据
    df = df[df["price"] > 0]
    df = df.dropna(subset=["title"])
    # 类型标准化
    df["price"] = df["price"].astype(float)
    df["original_price"] = df["original_price"].astype(float)
    df["discount_percentage"] = df["discount_percentage"].astype(float)
    df["sales"] = df["sales"].astype(int)
    df["reviews_count"] = df["reviews_count"].astype(int)
    df["rating"] = df["rating"].astype(float)
    df["amazon_choice"] = df["amazon_choice"].astype(int)
    df["best_seller"] = df["best_seller"].astype(int)
    df["prime_eligible"] = df["prime_eligible"].astype(int)
    print(f"DataFrame构建完成：共{len(df)}条有效记录（过滤空价格后）")
    return df


# ===================== 3. 数据预处理（整合AI关键词） =====================
def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """数据预处理：整合AI关键词+原有分词"""
    # 1. 分类拆分
    split_category = df["category"].str.split(">", n=1, expand=True)
    if split_category.shape[1] == 0:
        split_category = pd.DataFrame([""] * len(df), columns=["col1"]).assign(col2="")
    elif split_category.shape[1] == 1:
        split_category = split_category.assign(col2="")
    split_category.columns = ["category_1", "category_2"]
    df = pd.concat([df, split_category], axis=1)
    df["category_3"] = df.apply(
        lambda x: x["category_2"] if x["category_2"] != "" else x["category_1"],
        axis=1
    )

    # 2. 关键词整合
    stop_words = ['的', '适用', '专用', '款', '型', '为', '了', '适用于', 'for', 'with']

    def preprocess_title(text, ai_keywords):
        if pd.isna(text):
            return ""
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', ' ', text)
        words = jieba.lcut(text)
        words = [w for w in words if w not in stop_words and len(w) > 1]
        all_words = list(set(words + ai_keywords))
        return ' '.join(all_words)

    df["title_cut"] = df.apply(lambda x: preprocess_title(x["title"], x["ai_keywords"]), axis=1)

    # 3. 分箱逻辑（强制初始化列，避免缺失）
    # 价格分箱
    df["price_bin"] = None
    if len(df[df["price"] > 0]) > 0:
        df["price_bin"] = pd.cut(
            df["price"],
            bins=[0, 100, 300, 1000, float('inf')],
            labels=["低价(<100$)", "中价(100-300$)", "高价(300-1000$)", "超高价(>1000$)"],
            include_lowest=True,
            right=False
        ).astype(object)
    df["price_bin"] = df["price_bin"].fillna("未知价格")

    # 销量分箱
    df["sales_bin"] = None
    if len(df[df["sales"] >= 0]) > 0:
        df["sales_bin"] = pd.cut(
            df["sales"],
            bins=[0, 500, 2000, 5000, float('inf')],
            labels=["低销量(<500)", "中销量(500-2000)", "高销量(2000-5000)", "超高销量(>5000)"],
            include_lowest=True,
            right=False
        ).astype(object)
    df["sales_bin"] = df["sales_bin"].fillna("未知销量")

    # 折扣分箱
    df["discount_bin"] = None
    df["discount_bin"] = pd.cut(
        df["discount_percentage"],
        bins=[0, 5, 10, float('inf')],
        labels=["无折扣", "小折扣(5%)", "大折扣(>10%)"],
        include_lowest=True,
        right=False
    ).astype(object)
    df["discount_bin"] = df["discount_bin"].fillna("无折扣")

    # 评分分箱
    df["rating_bin"] = None
    if len(df[df["rating"] > 0]) > 0:
        df["rating_bin"] = pd.cut(
            df["rating"],
            bins=[0, 4.0, 4.5, 5.0],
            labels=["低分(<4.0)", "中分(4.0-4.5)", "高分(>4.5)"],
            include_lowest=True,
            right=False
        ).astype(object)
    df["rating_bin"] = df["rating_bin"].fillna("未知评分")

    return df


# ===================== 新增功能：标题模式与关键词组分析 =====================
def title_pattern_analysis(df: pd.DataFrame, client: OpenAI) -> Dict:
    """
    标题深度分析：
    1. 关键词组（N-Gram）统计
    2. 词组位置权重计算
    3. 标题行文风格分析
    """
    print("\n=== 新增：标题模式与关键词组深度分析 ===")
    result = {}
    valid_titles = df[df["title"] != ""]["title"].tolist()
    if not valid_titles:
        return {"error": "无有效标题数据"}

    # 1. 关键词组（N-Gram）统计（英文标题适配）
    vectorizer = CountVectorizer(ngram_range=(2, 3), stop_words='english')
    ngram_matrix = vectorizer.fit_transform(valid_titles)
    ngram_counts = ngram_matrix.sum(axis=0).A1
    ngram_freq = pd.Series(ngram_counts, index=vectorizer.get_feature_names_out()).sort_values(ascending=False)
    top_20_ngrams = ngram_freq.head(20).to_dict()
    result["关键词组频率"] = top_20_ngrams
    print("高频关键词组TOP10：", list(top_20_ngrams.keys())[:10])

    # 2. 词组位置权重计算
    position_weights = {}
    for title in valid_titles:
        words = re.sub(r'[^\w\s]', '', title.lower()).split()
        for idx, word in enumerate(words, 1):
            # 单词语权重（位置越靠前权重越高）
            weight = 1.0 / idx
            if word not in position_weights:
                position_weights[word] = 0.0
            position_weights[word] += weight
            # 2词组合权重
            if idx < len(words):
                phrase = f"{word} {words[idx]}"
                if phrase not in position_weights:
                    position_weights[phrase] = 0.0
                position_weights[phrase] += weight
    # 按权重排序
    position_weights = pd.Series(position_weights).sort_values(ascending=False).head(20).to_dict()
    result["词组位置权重"] = position_weights
    print("高位置权重词组TOP10：", list(position_weights.keys())[:10])

    # 3. 标题行文风格分析
    sample_titles = valid_titles[:10]
    prompt = f"""
    请分析以下亚马逊{str(CATEGORY_NAME)}商品标题的流行行文风格和结构模式，严格遵守：
    1. 总结常见的开头词、卖点排布顺序、常用句式
    2. 给出可直接复用的标题结构模板
    3. 语言简洁，适合运营人员参考

    标题示例：
    {chr(10).join(sample_titles)}
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=500
        )
        style_analysis = response.choices[0].message.content.strip()
        result["行文风格分析"] = style_analysis
        print("标题行文风格分析完成")
    except Exception as e:
        print(f" 风格分析失败：{e}")
        result["行文风格分析"] = "未获取到风格分析结果"

    return result


# ===================== 4. 多维度量化分析 =====================
def multi_dimension_analysis(df: pd.DataFrame, client: OpenAI) -> Dict:
    """核心量化分析：关键词+销量预测+关联规则+情感分析+标题模式分析"""
    analysis_result = {}

    # 4.1 关键词分析（TF-IDF+LDA）
    print("\n=== 1. 关键词与主题分析 ===")
    valid_title_cut = df[df["title_cut"] != ""]["title_cut"]
    keyword_freq = None
    keyword_score_df = None

    if len(valid_title_cut) == 0:
        analysis_result["关键词分析"] = {"error": "无有效标题分词数据"}
    else:
        # TF-IDF提取核心关键词
        tfidf = TfidfVectorizer(max_features=20)
        tfidf_matrix = tfidf.fit_transform(valid_title_cut)
        core_keywords = tfidf.get_feature_names_out().tolist()

        # LDA主题聚类
        texts = [text.split() for text in valid_title_cut]
        dictionary = corpora.Dictionary(texts)
        corpus = [dictionary.doc2bow(text) for text in texts]
        lda_model = models.LdaModel(corpus=corpus, id2word=dictionary, num_topics=3, random_state=42, passes=10)
        topics = [f"主题{idx + 1}：{topic}" for idx, topic in lda_model.print_topics(num_words=5)]

        # 关键词热度-竞争度评分（替换搜索量为评分+销量）
        keyword_freq = pd.Series([w for text in texts for w in text]).value_counts()
        top_10_keywords = keyword_freq.head(10).index.tolist()
        keyword_scores = []
        for kw in top_10_keywords:
            # 热度：包含该关键词的商品平均评分+平均销量归一化
            kw_products = df[df["title_cut"].str.contains(kw)]
            heat = (kw_products["rating"].mean() + (kw_products["sales"].mean() / 1000)) / 2
            competition = keyword_freq[kw] / keyword_freq.max()
            score = heat / (competition + 0.1)
            keyword_scores.append({
                "关键词": kw,
                "热度(归一化)": float(round(heat, 2)),
                "竞争度(0-1)": float(round(competition, 2)),
                "潜力评分": float(round(score, 2))
            })
        keyword_score_df = pd.DataFrame(keyword_scores).sort_values("潜力评分", ascending=False)

        # 保存结果
        analysis_result["关键词分析"] = {
            "核心关键词": core_keywords,
            "主题聚类": topics,
            "高潜力关键词": keyword_score_df.to_dict("records"),
            "关键词频率": {k: int(v) for k, v in keyword_freq.to_dict().items()}
        }
        print("核心关键词：", core_keywords)
        print("高潜力关键词TOP3：", keyword_score_df.head(3).to_dict("records"))

    # 4.2 标题模式与关键词组分析
    analysis_result["标题模式分析"] = title_pattern_analysis(df, client)

    # 4.3 销量预测与需求分析（替换特征：去掉search_volume，加入rating）
    print("\n=== 2. 销量预测与需求分析 ===")
    valid_features = df.dropna(subset=["price", "sales", "rating", "discount_percentage"])
    future_sales_pred_list = []
    price_sales_corr = 0.0

    if len(valid_features) < 5:  # 降低数据量要求适配相机数据
        analysis_result["销量分析"] = {
            "error": f"有效数据量不足（当前{len(valid_features)}条，需至少5条），无法进行销量预测"}
    else:
        features = ["price", "discount_percentage", "rating"]  # 替换为价格、折扣、评分
        X = valid_features[features]
        y = valid_features["sales"]
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # 训练XGBoost模型
        xgb_model = XGBRegressor(n_estimators=100, max_depth=5, learning_rate=0.1, random_state=42)
        xgb_model.fit(X_train, y_train)
        y_pred = xgb_model.predict(X_test)

        # 模型评估
        mae = float(round(mean_absolute_error(y_test, y_pred), 2))
        r2 = float(round(r2_score(y_test, y_pred), 2))
        price_sales_corr = float(round(valid_features[["price", "sales"]].corr().loc["price", "sales"], 2))

        # 未来价格带销量预测
        future_price_bands = pd.DataFrame({
            "price": [99, 199, 299],
            "discount_percentage": [5, 10, 15],
            "rating": [4.5, 4.6, 4.7]
        })
        future_sales_pred = xgb_model.predict(future_price_bands)
        future_sales_pred_list = [int(round(x)) for x in future_sales_pred]

        # 特征重要性
        feature_importance = [float(round(x, 3)) for x in xgb_model.feature_importances_]

        analysis_result["销量分析"] = {
            "模型评估": {"MAE": mae, "R²": r2},
            "价格-销量相关性": price_sales_corr,
            "未来价格带销量预测": [
                {"价格": 99, "折扣": 5, "评分": 4.5, "预测销量": future_sales_pred_list[0]},
                {"价格": 199, "折扣": 10, "评分": 4.6, "预测销量": future_sales_pred_list[1]},
                {"价格": 299, "折扣": 15, "评分": 4.7, "预测销量": future_sales_pred_list[2]}
            ],
            "特征重要性": dict(zip(features, feature_importance))
        }
        print(f"销量模型R²：{r2:.2f}（越接近1预测越准）")
        print(f"价格-销量相关性：{price_sales_corr:.2f}（负数表示价格越高销量越低）")

    # 4.4 价格-销量-评分-折扣关联规则分析
    print("\n=== 3. 价格-销量-评分-折扣关联规则分析 ===")
    assoc_df = pd.get_dummies(df[["price_bin", "sales_bin", "discount_bin", "rating_bin"]])

    # 降低最小支持度阈值，适配分散数据
    frequent_itemsets = apriori(assoc_df, min_support=0.05, use_colnames=True)

    if frequent_itemsets.empty:
        analysis_result["关联规则"] = {"error": "无满足最小支持度的频繁项集，无法生成关联规则"}
        print(" 无有效频繁项集，跳过关联规则分析")
    else:
        rules = association_rules(frequent_itemsets, metric='lift', min_threshold=1.0)
        core_rules = []
        for idx, row in rules.iterrows():
            antecedents = list(row["antecedents"])
            consequents = list(row["consequents"])
            if any("price_bin" in a or "discount_bin" in a or "rating_bin" in a for a in antecedents) and any(
                    "sales_bin" in c for c in consequents):
                core_rules.append({
                    "规则": f"{', '.join(antecedents)} → {', '.join(consequents)}",
                    "支持度": float(round(row["support"], 3)),
                    "置信度": float(round(row["confidence"], 3)),
                    "提升度": float(round(row["lift"], 3))
                })
        analysis_result["关联规则"] = core_rules if core_rules else {"提示": "无有效核心关联规则"}
        print("核心关联规则TOP3：", core_rules[:3] if core_rules else "无")

    # 4.5 评价情感分析
    print("\n=== 4. 评价情感分析 ===")

    def get_sentiment(text):
        if pd.isna(text):
            return "中性"
        s = SnowNLP(text)
        return "正面" if s.sentiments > 0.7 else "负面" if s.sentiments < 0.3 else "中性"

    df["sentiment"] = df["review"].apply(get_sentiment)
    sentiment_dist = {k: int(v) for k, v in df["sentiment"].value_counts().to_dict().items()}

    # 提取正负向核心词汇
    positive_words = []
    for review in df[df["sentiment"] == "正面"]["review"]:
        if pd.notna(review):
            words = jieba.lcut(review)
            positive_words.extend([w for w in words if len(w) > 1 and w not in ['的', '了', '很']])

    negative_words = []
    for review in df[df["sentiment"] == "负面"]["review"]:
        if pd.notna(review):
            words = jieba.lcut(review)
            negative_words.extend([w for w in words if len(w) > 1 and w not in ['的', '了', '很']])

    analysis_result["情感分析"] = {
        "情感分布": sentiment_dist,
        "正面核心词汇": {k: int(v) for k, v in
                         pd.Series(positive_words).value_counts().head(10).to_dict().items()} if positive_words else {},
        "负面核心词汇": {k: int(v) for k, v in
                         pd.Series(negative_words).value_counts().head(10).to_dict().items()} if negative_words else {}
    }
    print("情感分布：", sentiment_dist)
    print("用户核心痛点：", list(pd.Series(negative_words).value_counts().head(5).index) if negative_words else [])

    # 返回分析结果+辅助数据
    return analysis_result, {
        "keyword_freq": keyword_freq,
        "keyword_score_df": keyword_score_df,
        "valid_features": valid_features,
        "price_sales_corr": price_sales_corr,
        "future_price_list": [99, 199, 299],
        "future_sales_pred_list": future_sales_pred_list,
        "sentiment_dist": sentiment_dist,
        "df": df
    }


# ===================== 5. AI生成品类建议 =====================
def generate_category_suggestion(client: OpenAI, analysis_result: Dict, category_name: str = CATEGORY_NAME) -> str:
    """调用DeepSeek AI生成品类运营建议"""
    # 提取并校验各字段
    keyword_analysis = analysis_result.get('关键词分析', {})
    high_potential_kws = keyword_analysis.get('高潜力关键词', [])
    if not isinstance(high_potential_kws, list):
        high_potential_kws = []
    top3_high_potential = high_potential_kws[:3]

    core_kws = keyword_analysis.get('核心关键词', []) if isinstance(keyword_analysis.get('核心关键词'), list) else []
    topic_cluster = keyword_analysis.get('主题聚类', []) if isinstance(keyword_analysis.get('主题聚类'), list) else []

    # 标题模式分析结果
    title_pattern = analysis_result.get('标题模式分析', {})
    top_ngrams = list(title_pattern.get('关键词组频率', {}).keys())[:5]
    top_position_phrases = list(title_pattern.get('词组位置权重', {}).keys())[:5]
    style_analysis = title_pattern.get('行文风格分析', '')

    sales_analysis = analysis_result.get('销量分析', {})
    price_sales_corr = sales_analysis.get('价格-销量相关性', '无')
    price_forecast = sales_analysis.get('未来价格带销量预测', []) if isinstance(
        sales_analysis.get('未来价格带销量预测'), list) else []
    feature_importance = sales_analysis.get('特征重要性', {})

    association_rules = analysis_result.get('关联规则', []) if isinstance(analysis_result.get('关联规则'), list) else []

    sentiment_analysis = analysis_result.get('情感分析', {})
    sentiment_dist = sentiment_analysis.get('情感分布', {})
    pain_points = list(sentiment_analysis.get('负面核心词汇', {}).keys())[:5]
    advantages = list(sentiment_analysis.get('正面核心词汇', {}).keys())[:5]

    # 构造提示词
    prompt = f"""
    你是资深的亚马逊电商品类分析专家，现在需要基于以下{category_name}品类的量化分析结果，输出一份结构化的品类运营建议。
    分析结果：
    1. 关键词分析：
       - 核心关键词：{core_kws}
       - 高潜力关键词TOP3：{top3_high_potential}
       - 主题聚类：{topic_cluster}
    2. 标题模式分析：
       - 高频关键词组：{top_ngrams}
       - 高位置权重词组：{top_position_phrases}
       - 行文风格：{style_analysis}
    3. 销量分析：
       - 价格-销量相关性：{price_sales_corr}
       - 未来价格带销量预测：{price_forecast}
       - 特征重要性：{feature_importance}
    4. 关联规则：{association_rules[:3]}
    5. 情感分析：
       - 情感分布：{sentiment_dist}
       - 用户核心痛点：{pain_points}
       - 用户核心优点：{advantages}

    要求：
    1. 输出结构清晰，包含【选品建议】【定价建议】【运营建议】【产品优化建议】【标题优化建议】5个部分；
    2. 建议要具体、可落地，结合亚马逊平台特性和数据分析结果，不要空泛；
    3. 语言简洁，适合亚马逊运营人员阅读；
    4. 重点突出高潜力方向和需要规避的风险点；
    5. 【标题优化建议】需结合高频关键词组和位置权重给出具体优化方案。
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=5000
        )
        return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"调用DeepSeek AI失败：{str(e)}")


# ===================== AI生成亚马逊爆款长标题 =====================
def generate_hot_product_titles(client: OpenAI, category_name: str, suggestion: str) -> List[str]:
    """基于品类运营建议生成3-5个亚马逊爆款长标题"""
    prompt = f"""
    请基于以下{category_name}品类的运营建议，为亚马逊平台生成3-5个易大卖的爆款商品标题，严格遵守所有规则：

    ## 核心运营建议
    {suggestion}

    ## 标题创作规则
    1. 标题数量：必须是3-5个，不多不少
    2. 标题风格：包含多维度卖点（材质/功能/场景/风格/属性/现货等），符合亚马逊爆款标题特征
    3. 标题长度：每个标题字数20-40字，包含丰富的卖点关键词，无冗余虚词
    4. 输出格式：仅返回标题列表，每行一个，无其他任何解释、序号、标点或多余文字
    5. 核心要求：
       - 标题必须紧密贴合运营建议中的选品、定价、标题优化、产品优化方向
       - 优先融入运营建议中提到的高潜力关键词、最优价格带、核心卖点
       - 规避运营建议中提到的风险点（如用户痛点、低销量价格段）
       - 贴合{category_name}品类特性，突出核心卖点

    品类：{category_name}
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500,
        )
        # 解析标题列表
        title_content = response.choices[0].message.content.strip()
        titles = [title.strip() for title in title_content.split("\n") if
                  title.strip() and not title.startswith(("1.", "2.", "3.", "4.", "5.", "(", "（"))]

        # 校验标题数量
        if len(titles) < 3:
            supplement_titles = [
                f"爆款{category_name} 高性价比{category_name} {category_name}现货速发多场景适用",
                f"热销款{category_name} 贴合运营建议{category_name} 核心卖点{category_name}现货供应",
                f"优化款{category_name} 规避痛点{category_name} 高潜力关键词{category_name}便携实用款"
            ]
            titles += supplement_titles[:3 - len(titles)]
        elif len(titles) > 5:
            titles = titles[:5]

        print(f"\n=== AI基于运营建议生成{category_name}爆款长标题（3-5个）===")
        for idx, title in enumerate(titles, 1):
            print(f"{idx}. {title}")

        return titles
    except Exception as e:
        print(f"AI生成爆款标题失败：{e}，使用兜底标题")
        fallback_titles = [
            f"优化款{category_name} 高潜力关键词{category_name} 现货热销多场景适用{category_name}",
            f"爆款{category_name} 贴合运营建议{category_name} 核心卖点突出{category_name}现货速发",
            f"热销{category_name} 规避用户痛点{category_name} 高性价比{category_name}便携实用款"
        ]
        return fallback_titles


def generate_title_recommendation_score(client: OpenAI, titles: list, category_name: str, sales_analysis: dict,
                                        keyword_analysis: dict, title_pattern_analysis: dict) -> list:
    """AI分析并计算标题的推荐指数（0-10分）"""
    # 提取核心数据（增加容错）
    price_sales_corr = sales_analysis.get('价格-销量相关性', 0.0)
    feature_importance = sales_analysis.get('特征重要性', {})
    price_forecast = sales_analysis.get('未来价格带销量预测', [])

    high_potential_kws = keyword_analysis.get('高潜力关键词', [])
    if not isinstance(high_potential_kws, list):
        high_potential_kws = []
    valid_high_potential = [kw for kw in high_potential_kws if isinstance(kw, dict) and "关键词" in kw]

    core_kws = keyword_analysis.get('核心关键词', [])
    if not isinstance(core_kws, list):
        core_kws = []

    top_ngrams = list(title_pattern_analysis.get('关键词组频率', {}).keys())
    top_position_phrases = list(title_pattern_analysis.get('词组位置权重', {}).keys())

    # 构建评分Prompt
    prompt = f"""
    你是资深亚马逊运营专家，需基于{category_name}品类的销量关联数据和标题模式分析，为以下标题计算推荐指数（0-10分，保留2位小数）：
    ## 核心数据背景
    1. 价格-销量相关性：{price_sales_corr}（负数=价格越高销量越低，正数=价格越高销量越高）
    2. 销量影响特征重要性：{feature_importance}（数值越高对销量影响越大）
    3. 未来价格带销量预测：{price_forecast}
    4. 高潜力关键词（带潜力评分）：{valid_high_potential}
    5. 品类核心关键词：{core_kws}
    6. 高频关键词组：{top_ngrams}
    7. 高位置权重词组：{top_position_phrases}

    ## 评分规则
    1. 标题包含高潜力关键词/核心关键词/高频词组越多，分数越高
    2. 标题包含高位置权重词组且放置在靠前位置，分数越高
    3. 标题卖点贴合高权重销量特征（如价格、评分、折扣），分数越高
    4. 标题符合亚马逊爆款特征（卖点丰富、适配品类），分数越高
    5. 分数必须在0-10之间，保留2位小数

    ## 需要评分的标题列表
    {[f"{i + 1}. {title}" for i, title in enumerate(titles)]}

    ## 输出要求（必须严格遵守）
    仅返回JSON数组，无任何其他内容！格式示例：
    [{{"title": "标题1", "score": 8.50}}, {{"title": "标题2", "score": 7.80}}]
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        ai_content = response.choices[0].message.content.strip()
        ai_content = ai_content.replace("\n", "").replace("\t", "").strip()

        # 解析JSON
        score_list = json.loads(ai_content)
        # 校验格式
        if not isinstance(score_list, list) or len(score_list) != len(titles):
            raise ValueError(f"返回列表长度不匹配（预期{len(titles)}条）")

        # 校验并修正分数
        valid_score_list = []
        for idx, item in enumerate(score_list):
            if not isinstance(item, dict) or "title" not in item or "score" not in item:
                valid_score_list.append({"title": titles[idx], "score": 7.00})
            else:
                score = float(item["score"])
                score = max(0.0, min(10.0, score))
                valid_score_list.append({"title": item["title"], "score": round(score, 2)})

        print(f"\n=== {category_name}标题推荐指数评分结果 ===")
        for item in valid_score_list:
            print(f"标题：{item['title'][:50]}... | 推荐指数：{item['score']}/10.00")

        return valid_score_list

    except Exception as e:
        print(f"⚠️ 标题评分失败：{e}，使用兜底评分（7.0分）")
        fallback_score_list = [{"title": title, "score": 7.00} for title in titles]
        return fallback_score_list


def main():
    """主函数：整合所有分析流程"""
    print("===== 亚马逊商品数据分析系统启动 =====")
    try:
        # 1. 初始化DeepSeek客户端
        client = init_deepseek_client()
        print("✅ 步骤1/9：DeepSeek客户端初始化完成")

        # 2. 读取JSON数据
        raw_data = read_amazon_json(JSON_FILE_PATH)
        print("✅ 步骤2/9：JSON数据读取完成")

        # 3. 清洗空值字段
        cleaned_products = clean_empty_fields(raw_data)
        if not cleaned_products:
            raise ValueError("清洗后无有效商品数据，终止分析")
        print("✅ 步骤3/9：数据清洗完成")

        # 4. 转换为DataFrame（含真实销量/评论数处理）
        df = json_to_dataframe(cleaned_products, client)
        print("✅ 步骤4/9：DataFrame构建完成")

        # 5. 数据预处理
        df = preprocess_data(df)
        print("✅ 步骤5/9：数据预处理完成")

        # 6. 多维度量化分析
        analysis_result, visual_data = multi_dimension_analysis(df, client)
        print("✅ 步骤6/9：多维度量化分析完成")

        # 7. AI生成品类运营建议
        suggestion = generate_category_suggestion(client, analysis_result)
        print("\n=== AI生成的品类运营建议 ===")
        print(suggestion)
        print("✅ 步骤7/9：品类运营建议生成完成")

        # 8. AI生成爆款长标题
        hot_titles = generate_hot_product_titles(client, CATEGORY_NAME, suggestion)
        print("✅ 步骤8/9：爆款标题生成完成")

        # 9. 标题推荐指数评分
        title_pattern_analysis_result = analysis_result.get("标题模式分析", {})
        keyword_analysis_result = analysis_result.get("关键词分析", {})
        sales_analysis_result = analysis_result.get("销量分析", {})
        title_scores = generate_title_recommendation_score(
            client, hot_titles, CATEGORY_NAME,
            sales_analysis_result, keyword_analysis_result, title_pattern_analysis_result
        )
        print("✅ 步骤9/9：标题推荐指数评分完成")

        print("\n===== 亚马逊商品数据分析系统执行完毕 =====")
        # 保存最终分析结果
        final_result = {
            "品类名称": CATEGORY_NAME,
            "分析结果": analysis_result,
            "爆款标题及评分": title_scores,
            "运营建议": suggestion
        }
        save_path = f"{CATEGORY_NAME}_最终分析结果.json"
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(final_result, f, ensure_ascii=False, indent=4)
        print(f"📁最终分析结果已保存至：{save_path}")

    except Exception as e:
        print(f"\n分析流程执行失败：{str(e)}")
        raise


# 程序入口
if __name__ == "__main__":
    main()