"""
测试 Amazon 商品详情爬虫
"""
import json
import pandas as pd
from pathlib import Path
from amazon_detail_crawler import AmazonDetailCrawler


def test_single_product():
    """测试爬取单个商品"""
    print("="*60)
    print("测试：爬取单个商品详情")
    print("="*60)
    
    # 创建爬虫实例（接管模式）
    crawler = AmazonDetailCrawler(local_port=9333)
    
    try:
        # 测试 ASIN
        test_asin = 'B0CTJGJL2T' 
        
        # 爬取商品
        product = crawler.crawl_product(test_asin)
        
        # 打印结果
        print("\n" + "="*60)
        print("爬取结果")
        print("="*60)
        print(f"ASIN: {product['asin']}")
        print(f"标题: {product['title']}")
        print(f"价格: {product['price']}")
        print(f"\n五点描述 ({len(product['bullet_points'])} 条):")
        for i, bullet in enumerate(product['bullet_points'], 1):
            print(f"  {i}. {bullet[:80]}...")
        
        # 打印分组后的商品属性
        print(f"\n商品属性 ({len(product['product_details'])} 个表格):")
        for table_name, table_data in product['product_details'].items():
            print(f"\n  [{table_name}] ({len(table_data)} 项):")
            # 只显示每个表格的前3项
            for i, (key, value) in enumerate(list(table_data.items())[:3]):
                print(f"    {key}: {value}")
            if len(table_data) > 3:
                print(f"    ... (还有 {len(table_data) - 3} 项)")
        
        print(f"\nA+ 图片: {len(product['aplus_images'])} 张")
        
        # 保存结果到 JSON 文件
        output_file = Path(__file__).parent / f'test_product_{test_asin}.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(product, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 结果已保存到: {output_file}")
        
    finally:
        crawler.close()


def test_multiple_products():
    """测试批量爬取多个商品"""
    print("="*60)
    print("测试：批量爬取多个商品")
    print("="*60)
    
    # 创建爬虫实例（接管模式）
    crawler = AmazonDetailCrawler(local_port=9333)
    
    try:
        # 测试 ASIN 列表
        test_asins = [
        
            'B08XQ4FQTP',  # 添加第二个测试 ASIN
                'B0DQKSVC1B',
        ]
        
        # 批量爬取
        products = crawler.crawl_products_from_list(
            asins=test_asins,
            output_file='test_amazon_products.json'
        )
        
        print(f"\n✅ 成功爬取 {len(products)} 个商品")
        
    finally:
        crawler.close()


def read_asins_from_excel(excel_path: str, column_name: str = "#1 前三ASIN") -> list:
    """
    从 Excel 读取 ASIN 列表
    
    Args:
        excel_path: Excel 文件路径
        column_name: 包含 ASIN 的列名
        
    Returns:
        ASIN 列表
    """
    try:
        # 读取 Excel 文件
        df = pd.read_excel(excel_path)
        
        # 检查列是否存在
        if column_name not in df.columns:
            print(f"❌ 错误：未找到列 '{column_name}'")
            print(f"可用的列: {', '.join(df.columns.tolist())}")
            return []
        
        # 提取 ASIN 列，去掉空值
        asins = df[column_name].dropna().astype(str).tolist()
        
        # 去掉空字符串和空格
        asins = [asin.strip() for asin in asins if asin.strip()]
        
        return asins
    
    except Exception as e:
        print(f"❌ 读取 Excel 文件失败: {e}")
        return []


def test_excel_crawl():
    """从 Excel 读取 ASIN 并批量爬取"""
    print("="*60)
    print("测试：从 Excel 读取 ASIN 批量爬取")
    print("="*60)
    
    # Excel 文件路径
    excel_file = Path(__file__).parent / 'KeywordMining-US-bedroom-desk-Last-30-days-233298.xlsx'
    
    if not excel_file.exists():
        print(f"❌ Excel 文件不存在: {excel_file}")
        return
    
    # 读取 ASIN 列表
    print(f"\n正在读取 Excel 文件: {excel_file.name}")
    all_asins = read_asins_from_excel(str(excel_file))
    
    if not all_asins:
        print("❌ 未读取到任何 ASIN")
        return
    
    print(f"✅ 共读取到 {len(all_asins)} 个 ASIN")
    
    # 显示前5个和后5个作为预览
    print("\n预览 ASIN:")
    preview_count = min(5, len(all_asins))
    for i in range(preview_count):
        print(f"  {i+1}. {all_asins[i]}")
    if len(all_asins) > 10:
        print("  ...")
        for i in range(max(preview_count, len(all_asins) - 5), len(all_asins)):
            print(f"  {i+1}. {all_asins[i]}")
    
    # 询问用户要爬取的范围
    print("\n" + "="*60)
    print("选择要爬取的条目范围")
    print("="*60)
    
    while True:
        try:
            start_input = input(f"起始位置 (1-{len(all_asins)}) [1]: ").strip() or "1"
            start_idx = int(start_input)
            
            end_input = input(f"结束位置 (1-{len(all_asins)}) [{len(all_asins)}]: ").strip() or str(len(all_asins))
            end_idx = int(end_input)
            
            # 验证范围
            if start_idx < 1 or start_idx > len(all_asins):
                print(f"❌ 起始位置必须在 1 到 {len(all_asins)} 之间")
                continue
            
            if end_idx < 1 or end_idx > len(all_asins):
                print(f"❌ 结束位置必须在 1 到 {len(all_asins)} 之间")
                continue
            
            if start_idx > end_idx:
                print("❌ 起始位置不能大于结束位置")
                continue
            
            break
            
        except ValueError:
            print("❌ 请输入有效的数字")
    
    # 提取指定范围的 ASIN (转换为0-based索引)
    selected_asins = all_asins[start_idx-1:end_idx]
    
    print(f"\n✅ 已选择第 {start_idx} 到第 {end_idx} 条，共 {len(selected_asins)} 个 ASIN")
    print("\n将要爬取的 ASIN:")
    for i, asin in enumerate(selected_asins[:10], start_idx):
        print(f"  {i}. {asin}")
    if len(selected_asins) > 10:
        print(f"  ... (还有 {len(selected_asins) - 10} 个)")
    
    # 确认开始爬取
    confirm = input("\n确认开始爬取? (y/n) [y]: ").strip().lower() or "y"
    if confirm != 'y':
        print("❌ 已取消爬取")
        return
    
    # 创建爬虫实例（接管模式）
    print("\n正在初始化爬虫...")
    crawler = AmazonDetailCrawler(local_port=9333)
    
    try:
        # 批量爬取
        products = crawler.crawl_products_from_list(
            asins=selected_asins,
            output_file=f'amazon_products_{start_idx}_to_{end_idx}.json'
        )
        
        print("\n" + "="*60)
        print("爬取完成")
        print("="*60)
        print(f"✅ 成功爬取 {len(products)} 个商品")
        
    finally:
        crawler.close()


if __name__ == '__main__':
    print("\n⚠️  使用前请确保：")
    print("1. 已启动 Edge 浏览器调试模式（端口 9333）")
    print("   运行: ..\\sellerSprite\\启动Chrome调试模式.bat")
    print("2. 或手动启动: msedge.exe --remote-debugging-port=9333 --remote-allow-origins=*")
    print()
    
    # 选择测试模式
    print("选择测试模式:")
    print("  1. 单个商品测试")
    print("  2. 批量爬取（手动输入ASIN）")
    print("  3. 从 Excel 读取并批量爬取")
    choice = input("\n请选择 (1/2/3) [3]: ").strip() or "3"
    
    if choice == "1":
        test_single_product()
    elif choice == "2":
        test_multiple_products()
    elif choice == "3":
        test_excel_crawl()
    else:
        print("❌ 无效的选择")
