import os
import shutil
import torch
import clip
from PIL import Image
import torch.nn.functional as F
from tqdm import tqdm

# ======================================================
# 1️⃣ 路径配置（你只需要改这里）
# ======================================================

# 文件夹 A：仅 1 张查询图片
FOLDER_A = r"C:\agent_development\amazon_decrypt-main_1\encrypt_decrypt\Amazon_add1\1\ecommerce_data\amazon\image_target"

# 文件夹 B：素材库（多张图片）
FOLDER_B = r"C:\agent_development\amazon_decrypt-main_1\encrypt_decrypt\Amazon_add1\1\ecommerce_data\amazon\images"

# 文件夹 C：输出相似图片
FOLDER_C = r"C:\agent_development\amazon_decrypt-main_1\encrypt_decrypt\Amazon_add1\1\ecommerce_data\amazon\images_result"

# 取最相似的前 K 张
TOP_K = 5

# ======================================================
# 2️⃣ 设备选择
# ======================================================
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# ======================================================
# 3️⃣ 加载 CLIP 模型（使用你已有的 ViT-B-32.pt）
# ======================================================
model, preprocess = clip.load(
    "ViT-B/32",
    device=DEVICE,
    download_root=r"C:\image_lib"   # 如果 .pt 已在默认缓存，会直接用
)

model.eval()

# ======================================================
# 4️⃣ 工具函数
# ======================================================

def load_image(image_path):
    """
    加载并预处理单张图片
    """
    image = Image.open(image_path).convert("RGB")
    image = preprocess(image).unsqueeze(0).to(DEVICE)
    return image


def extract_feature(image_tensor):
    """
    提取并归一化图片特征
    """
    with torch.no_grad():
        feature = model.encode_image(image_tensor)
        feature = F.normalize(feature, dim=-1)
    return feature


# ======================================================
# 5️⃣ 主流程
# ======================================================
def main():
    # 创建输出目录 C（如果不存在）
    os.makedirs(FOLDER_C, exist_ok=True)

    # -------------------------------
    # ① 读取文件夹 A 中的查询图片
    # -------------------------------
    query_images = os.listdir(FOLDER_A)
    if len(query_images) != 1:
        raise ValueError("文件夹 A 中必须且只能有一张图片")

    query_image_path = os.path.join(FOLDER_A, query_images[0])
    query_image_tensor = load_image(query_image_path)
    query_feature = extract_feature(query_image_tensor)

    # -------------------------------
    # ② 遍历文件夹 B，计算相似度
    # -------------------------------
    results = []

    for img_name in tqdm(os.listdir(FOLDER_B), desc="Searching in B"):
        img_path = os.path.join(FOLDER_B, img_name)

        try:
            img_tensor = load_image(img_path)
            img_feature = extract_feature(img_tensor)

            # 余弦相似度（CLIP 已归一化，可直接点积）
            similarity = (query_feature @ img_feature.T).item()
            results.append((img_name, similarity))

        except Exception as e:
            print(f"跳过 {img_name}，原因：{e}")

    # -------------------------------
    # ③ 排序，选最相似的 TOP_K
    # -------------------------------
    results.sort(key=lambda x: x[1], reverse=True)

    print("\n最相似的图片：")
    for i, (name, score) in enumerate(results[:TOP_K], start=1):
        print(f"{i}. {name} | 相似度 = {score:.4f}")

        # -------------------------------
        # ④ 复制到文件夹 C
        # -------------------------------
        shutil.copy(
            os.path.join(FOLDER_B, name),
            os.path.join(FOLDER_C, name)
        )

    print("\n✅ 相似图片已复制到文件夹 C")


# ======================================================
# 6️⃣ 程序入口
# ======================================================
if __name__ == "__main__":
    main()
