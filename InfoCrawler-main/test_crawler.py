#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Amazon 爬虫测试脚本 - 使用 Microsoft Edge 浏览器
"""

import os
import sys
from amazon_search_crawler import AmazonSearchCrawler
import json


def test_search():
    """测试搜索功能 - 使用 Microsoft Edge 浏览器"""
    print("=" * 60)
    print("Amazon 商品搜索测试")
    print("浏览器: Microsoft Edge")
    print("模式: 自动启动")
    print("=" * 60)

    try:
        # ========== 检查 Edge 浏览器 ==========
        print("\n🔍 检查 Microsoft Edge 浏览器...")

        edge_paths = [
            r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
            r'C:\Users\{}\AppData\Local\Microsoft\Edge\Application\msedge.exe'.format(os.getlogin()),
        ]

        edge_found = False
        for path in edge_paths:
            if os.path.exists(path):
                print(f"✅ 找到 Microsoft Edge: {path}")
                edge_found = True
                break

        if not edge_found:
            print("⚠️ 未找到 Microsoft Edge，将尝试系统默认浏览器")

        # 创建爬虫实例 - 使用接管模式（端口9333）
        print("\n🚀 尝试接管 Edge 浏览器（端口: 9333）...")
        print("💡 如果接管失败，将自动启动新浏览器")

        try:
            # 先尝试接管模式（如果Edge已用调试模式启动）
            crawler = AmazonSearchCrawler(
                headless=False,  # 显示浏览器窗口，便于观察
                local_port=9333  # 接管模式端口
            )
            print("✅ 成功接管 Edge 浏览器")
        except Exception as e:
            print(f"❌ 接管失败: {e}")
            print("\n🔄 正在自动启动 Edge 浏览器...")

            # 接管失败，使用自动启动模式
            crawler = AmazonSearchCrawler(
                headless=False,  # 显示浏览器窗口
                browser_type='edge'  # 指定使用Edge浏览器
            )
            print("✅ Edge 浏览器已自动启动")

        # 测试搜索关键词和最大页数
        keyword = "airplane"
        max_pages = 2

        print(f"\n{'=' * 60}")
        print(f"开始测试搜索: {keyword}")
        print(f"最大爬取页数: {max_pages}")
        print(f"{'=' * 60}\n")

        # 执行搜索
        results = crawler.search_products(keyword, max_pages=max_pages)

        # 输出结果
        print(f"\n{'=' * 60}")
        print(f"搜索完成！共获取 {len(results)} 个商品")
        print(f"{'=' * 60}\n")

        if results:
            # 显示前3个商品的详细信息
            for i, product in enumerate(results[:3], 1):
                print(f"商品 {i}:")
                print(f"  标题: {product.get('title', 'N/A')}")
                print(f"  价格: {product.get('price', 'N/A')}")
                print(f"  ASIN: {product.get('asin', 'N/A')}")
                print(f"  评分: {product.get('rating', 'N/A')}")
                print(f"  评论数: {product.get('review_count', 'N/A')}")
                detail_url = product.get('detail_url', 'N/A')
                print(f"  详情链接: {detail_url[:80] + '...' if detail_url and detail_url != 'N/A' else detail_url}")
                image_url = product.get('image_url', 'N/A')
                print(f"  图片链接: {image_url[:80] + '...' if image_url and image_url != 'N/A' else image_url}")
                print()

            # 保存结果到 JSON 文件
            output_file = f"amazon_results_{keyword.replace(' ', '_')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)

            print(f"✅ 结果已保存到: {output_file}")
        else:
            print("⚠️ 未获取到任何商品数据")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # 关闭浏览器
        if 'crawler' in locals():
            print("\n正在关闭浏览器...")
            try:
                crawler.close()
                print("✅ 浏览器已关闭")
            except:
                print("⚠️ 关闭浏览器时出错")


if __name__ == "__main__":
    test_search()