import pandas as pd
import os

# 创建测试数据
test_data = {
    "ASIN": ["B08N5WRWNW", "B08N5WPMQ2", "B07VGRJDFY", "B083ZH2B7H"],
    "Product Name": ["Example Product 1", "Example Product 2", "Example Product 3", "Example Product 4"],
    "Category": ["Electronics", "Home", "Office", "Gaming"]
}

df = pd.DataFrame(test_data)

# 保存到 Excel
excel_path = "KeywordMining-US-bedroom-desk-Last-30-days-233298.xlsx"
df.to_excel(excel_path, index=False)

print(f"✅ 测试 Excel 文件已创建: {excel_path}")
print(f"📁 位置: {os.path.abspath(excel_path)}")
print("\n📋 文件内容:")
print(df)
