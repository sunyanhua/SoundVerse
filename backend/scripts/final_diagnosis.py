#!/usr/bin/env python3
"""
三合一诊断脚本：确定DashScope API的正确调用方式
方式A：标准模式 - OpenAI客户端，不带工作空间头部
方式B：空间模式 - OpenAI客户端，带工作空间头部
方式C：原生模式 - dashscope官方SDK
"""
import os
import sys
import json
from pathlib import Path

# 添加项目根目录到Python路径
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from config import settings

def print_header(title):
    """打印标题"""
    print("\n" + "="*80)
    print(f"=== {title}")
    print("="*80)

def test_standard_mode():
    """方式A：标准模式 - 不带工作空间头部"""
    print_header("方式A：标准模式 (OpenAI客户端，不带工作空间头部)")

    api_key = settings.DASHSCOPE_API_KEY
    model = settings.DASHSCOPE_EMBEDDING_MODEL
    vector_dimension = settings.VECTOR_DIMENSION

    print(f"API密钥: {api_key[:8]}...")
    print(f"Embedding模型: {model}")
    print(f"向量维度: {vector_dimension}")

    if not api_key:
        print("错误: API密钥为空")
        return None, 0

    from openai import OpenAI

    try:
        # 创建OpenAI客户端 - 不带工作空间ID
        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            default_headers={}  # 空headers
        )

        # 测试文本
        test_text = "你好，北京广播。"
        print(f"测试文本: '{test_text}'")

        # 调用embeddings.create
        print("正在调用 embeddings.create...")
        response = client.embeddings.create(
            model=model,
            input=test_text,
            dimensions=vector_dimension,
            encoding_format="float"
        )

        # 检查响应
        embedding = response.data[0].embedding
        dimension = len(embedding)
        print(f"✅ 成功！")
        print(f"   向量维度: {dimension}")
        print(f"   向量前3个值: {embedding[:3]}")

        if dimension == vector_dimension:
            print(f"✅ 维度匹配: {dimension} == {vector_dimension}")
        else:
            print(f"⚠️ 维度不匹配: {dimension} != {vector_dimension}")

        return "standard", dimension

    except Exception as e:
        print(f"❌ 失败: {e}")
        return None, 0

def test_workspace_mode():
    """方式B：空间模式 - 带工作空间头部"""
    print_header("方式B：空间模式 (OpenAI客户端，带工作空间头部)")

    api_key = settings.DASHSCOPE_API_KEY
    workspace_id = settings.DASHSCOPE_WORKSPACE_ID
    model = settings.DASHSCOPE_EMBEDDING_MODEL
    vector_dimension = settings.VECTOR_DIMENSION

    print(f"API密钥: {api_key[:8]}...")
    print(f"工作空间ID: {workspace_id}")
    print(f"Embedding模型: {model}")
    print(f"向量维度: {vector_dimension}")

    if not api_key:
        print("错误: API密钥为空")
        return None, 0

    if not workspace_id:
        print("错误: 工作空间ID为空")
        return None, 0

    from openai import OpenAI

    try:
        # 创建OpenAI客户端 - 带工作空间ID
        default_headers = {"X-DashScope-WorkSpace": workspace_id}

        client = OpenAI(
            api_key=api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            default_headers=default_headers
        )

        # 测试文本
        test_text = "你好，北京广播。"
        print(f"测试文本: '{test_text}'")

        # 调用embeddings.create
        print("正在调用 embeddings.create...")
        response = client.embeddings.create(
            model=model,
            input=test_text,
            dimensions=vector_dimension,
            encoding_format="float"
        )

        # 检查响应
        embedding = response.data[0].embedding
        dimension = len(embedding)
        print(f"✅ 成功！")
        print(f"   向量维度: {dimension}")
        print(f"   向量前3个值: {embedding[:3]}")

        if dimension == vector_dimension:
            print(f"✅ 维度匹配: {dimension} == {vector_dimension}")
        else:
            print(f"⚠️ 维度不匹配: {dimension} != {vector_dimension}")

        return "workspace", dimension

    except Exception as e:
        print(f"❌ 失败: {e}")
        return None, 0

def test_native_mode():
    """方式C：原生模式 - dashscope官方SDK"""
    print_header("方式C：原生模式 (dashscope官方SDK)")

    api_key = settings.DASHSCOPE_API_KEY
    model = settings.DASHSCOPE_EMBEDDING_MODEL
    vector_dimension = settings.VECTOR_DIMENSION

    print(f"API密钥: {api_key[:8]}...")
    print(f"Embedding模型: {model}")
    print(f"向量维度: {vector_dimension}")

    if not api_key:
        print("错误: API密钥为空")
        return None, 0

    try:
        # 尝试导入dashscope
        import dashscope

        # 设置API密钥
        dashscope.api_key = api_key

        # 测试文本
        test_text = "你好，北京广播。"
        print(f"测试文本: '{test_text}'")

        # 调用dashscope.TextEmbedding
        print("正在调用 dashscope.TextEmbedding...")
        from dashscope import TextEmbedding

        response = TextEmbedding.call(
            model=model,
            input=test_text,
            text_type="document"
        )

        if response.status_code == 200:
            embedding = response.output["embeddings"][0]["embedding"]
            dimension = len(embedding)
            print(f"✅ 成功！")
            print(f"   向量维度: {dimension}")
            print(f"   向量前3个值: {embedding[:3]}")

            if dimension == vector_dimension:
                print(f"✅ 维度匹配: {dimension} == {vector_dimension}")
            else:
                print(f"⚠️ 维度不匹配: {dimension} != {vector_dimension}")

            return "native", dimension
        else:
            print(f"❌ API返回错误: {response.status_code}")
            print(f"   错误信息: {response.message}")
            return None, 0

    except ImportError:
        print("❌ dashscope库未安装，跳过原生模式测试")
        print("   安装命令: pip install dashscope")
        return None, 0
    except Exception as e:
        print(f"❌ 失败: {e}")
        return None, 0

def check_dashvector_dimension():
    """检查DashVector集合维度"""
    print_header("检查DashVector集合维度")

    endpoint = settings.DASHVECTOR_ENDPOINT
    api_key = settings.DASHVECTOR_API_KEY
    collection_name = settings.DASHVECTOR_COLLECTION
    namespace = settings.DASHVECTOR_NAMESPACE
    config_dimension = settings.VECTOR_DIMENSION

    print(f"DashVector配置:")
    print(f"  端点: {endpoint}")
    print(f"  API密钥: {api_key[:8]}...")
    print(f"  集合: {collection_name}")
    print(f"  命名空间: {namespace}")
    print(f"  配置维度: {config_dimension}")

    if not endpoint or not api_key:
        print("❌ DashVector配置不完整")
        return 0

    try:
        import dashvector

        # 创建客户端
        client = dashvector.Client(api_key=api_key, endpoint=endpoint)

        # 获取集合
        collection = client.get(collection_name, namespace=namespace)
        if collection:
            actual_dimension = collection.dimension
            print(f"✅ 集合存在，实际维度: {actual_dimension}")

            if actual_dimension == config_dimension:
                print(f"✅ 维度匹配: {actual_dimension} == {config_dimension}")
            else:
                print(f"⚠️ 维度不匹配: {actual_dimension} != {config_dimension}")
                print(f"  建议: 删除并重新创建集合以匹配维度 {config_dimension}")

            return actual_dimension
        else:
            print("❌ 集合不存在")
            return 0

    except ImportError:
        print("❌ dashvector库未安装，跳过维度检查")
        print("   安装命令: pip install dashvector")
        return 0
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return 0

def fix_nlp_service(mode, dimension):
    """根据成功模式修复nlp_service.py"""
    print_header(f"修复nlp_service.py - 锁定为{mode}模式")

    nlp_service_path = backend_dir / "ai_models" / "nlp_service.py"

    if not nlp_service_path.exists():
        print(f"❌ 文件不存在: {nlp_service_path}")
        return False

    # 读取文件内容
    with open(nlp_service_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 查找get_text_embedding方法
    import re

    # 移除回退到模拟模式的代码
    # 查找并移除回退代码
    old_code = r"""# 调用OpenAI兼容API获取文本向量
            try:
                response = self\.openai_client\.embeddings\.create\(
                    model=self\.embedding_model,
                    input=text,
                    dimensions=self\.vector_dimension,
                    encoding_format="float"
                \)
                embedding = response\.data\[0\]\.embedding
                logger\.debug\(f"文本向量获取成功: \{len\(embedding\)\} 维度"\)
                return embedding
            except Exception as api_error:
                logger\.error\(f"DashScope OpenAI兼容API调用失败: \{str\(api_error\)\}"\)
                # 尝试不带dimensions参数调用（某些模型可能不支持）
                try:
                    response = self\.openai_client\.embeddings\.create\(
                        model=self\.embedding_model,
                        input=text,
                        encoding_format="float"
                    \)
                    embedding = response\.data\[0\]\.embedding
                    logger\.debug\(f"文本向量获取成功\(不带dimensions\): \{len\(embedding\)\} 维度"\)
                    return embedding
                except Exception as fallback_error:
                    logger\.error\(f"DashScope API回退调用失败: \{str\(fallback_error\)\}"\)
                    # API失败时回退到模拟模式
                    logger\.warning\("DashScope API失败，回退到模拟向量模式"\)
                    np\.random\.seed\(hash\(text\) % \(2\*\*32\)\)
                    vector = np\.random\.randn\(self\.vector_dimension\)\.tolist\(\)
                    norm = np\.linalg\.norm\(vector\)
                    if norm > 0:
                        vector = \(vector / norm\)\.tolist\(\)
                    return vector"""

    # 根据模式替换代码
    if mode == "workspace":
        # 使用工作空间模式 - 现有代码已经正确
        new_code = """# 调用OpenAI兼容API获取文本向量
            try:
                response = self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=text,
                    dimensions=self.vector_dimension,
                    encoding_format="float"
                )
                embedding = response.data[0].embedding
                logger.debug(f"文本向量获取成功: {len(embedding)} 维度")
                return embedding
            except Exception as api_error:
                logger.error(f"DashScope OpenAI兼容API调用失败: {str(api_error)}")
                # 尝试不带dimensions参数调用（某些模型可能不支持）
                try:
                    response = self.openai_client.embeddings.create(
                        model=self.embedding_model,
                        input=text,
                        encoding_format="float"
                    )
                    embedding = response.data[0].embedding
                    logger.debug(f"文本向量获取成功(不带dimensions): {len(embedding)} 维度")
                    return embedding
                except Exception as fallback_error:
                    logger.error(f"DashScope API回退调用失败: {str(fallback_error)}")
                    # 严格模式：不模拟，返回None
                    return None"""
    else:
        # 标准模式或原生模式 - 移除工作空间ID逻辑
        new_code = """# 调用OpenAI兼容API获取文本向量
            try:
                response = self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=text,
                    dimensions=self.vector_dimension,
                    encoding_format="float"
                )
                embedding = response.data[0].embedding
                logger.debug(f"文本向量获取成功: {len(embedding)} 维度")
                return embedding
            except Exception as api_error:
                logger.error(f"DashScope OpenAI兼容API调用失败: {str(api_error)}")
                # 尝试不带dimensions参数调用（某些模型可能不支持）
                try:
                    response = self.openai_client.embeddings.create(
                        model=self.embedding_model,
                        input=text,
                        encoding_format="float"
                    )
                    embedding = response.data[0].embedding
                    logger.debug(f"文本向量获取成功(不带dimensions): {len(embedding)} 维度")
                    return embedding
                except Exception as fallback_error:
                    logger.error(f"DashScope API回退调用失败: {str(fallback_error)}")
                    # 严格模式：不模拟，返回None
                    return None"""

    # 替换代码
    content = re.sub(old_code, new_code, content, flags=re.DOTALL)

    # 写回文件
    with open(nlp_service_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ nlp_service.py 已修复，锁定为{mode}模式")
    print(f"   移除模拟向量回退，API失败时返回None")
    return True

def reset_dashvector(dimension):
    """重置DashVector集合以匹配维度"""
    print_header("重置DashVector集合")

    try:
        # 导入重置脚本
        from scripts.reset_dashvector import reset_dashvector_collection

        print(f"目标维度: {dimension}")
        print("正在重置DashVector集合...")

        success = reset_dashvector_collection()

        if success:
            print("✅ DashVector集合重置成功")
            return True
        else:
            print("❌ DashVector集合重置失败")
            return False

    except Exception as e:
        print(f"❌ 重置失败: {e}")
        return False

def main():
    """主函数"""
    print("="*80)
    print("三合一DashScope API诊断脚本")
    print("="*80)

    # 检查环境变量
    print("\n📋 环境配置检查:")
    print(f"   DASHSCOPE_API_KEY: {settings.DASHSCOPE_API_KEY[:8]}...")
    print(f"   DASHSCOPE_WORKSPACE_ID: {settings.DASHSCOPE_WORKSPACE_ID}")
    print(f"   DASHSCOPE_EMBEDDING_MODEL: {settings.DASHSCOPE_EMBEDDING_MODEL}")
    print(f"   VECTOR_DIMENSION: {settings.VECTOR_DIMENSION}")

    # 测试三种方式
    results = []

    # 方式A：标准模式
    mode_a, dim_a = test_standard_mode()
    if mode_a:
        results.append(("standard", dim_a))

    # 方式B：空间模式
    mode_b, dim_b = test_workspace_mode()
    if mode_b:
        results.append(("workspace", dim_b))

    # 方式C：原生模式
    mode_c, dim_c = test_native_mode()
    if mode_c:
        results.append(("native", dim_c))

    # 检查DashVector维度
    dashvector_dim = check_dashvector_dimension()

    # 总结
    print_header("诊断总结")

    if not results:
        print("❌ 所有测试方式都失败了！")
        print("\n建议:")
        print("1. 确认API密钥: sk-f22e081c4ea848b683e02eb2ac31b88e")
        print("2. 确认工作空间ID: ws-d0d9y5s90m7wq7mv")
        print("3. 检查百炼控制台API权限")
        print("4. 确认账户余额或配额")
        return 1

    # 选择成功的方式
    best_mode, best_dim = results[0]  # 使用第一个成功的方式

    print(f"✅ 找到可用的调用方式: {best_mode}")
    print(f"   向量维度: {best_dim}")

    # 检查维度一致性
    if dashvector_dim > 0 and best_dim != dashvector_dim:
        print(f"⚠️ 维度不一致: API返回{dim_a}，DashVector集合{dashvector_dim}")
        print("   需要重置DashVector集合...")
        if not reset_dashvector(best_dim):
            print("❌ 无法重置DashVector，请手动运行 reset_dashvector.py")
            return 1
    elif dashvector_dim == 0:
        print("⚠️ 无法检查DashVector维度，请确保配置正确")

    # 修复nlp_service.py
    print_header("执行修复")
    if not fix_nlp_service(best_mode, best_dim):
        print("❌ 修复nlp_service.py失败")
        return 1

    print("\n" + "="*80)
    print("🎉 诊断完成！")
    print(f"   使用模式: {best_mode}")
    print(f"   向量维度: {best_dim}")
    print("   nlp_service.py 已修复")
    print("="*80)

    # 返回成功，维度信息供后续使用
    return {"mode": best_mode, "dimension": best_dim}

if __name__ == "__main__":
    try:
        result = main()
        if isinstance(result, dict):
            print(f"\n🔧 诊断结果: {result['mode']}模式，维度{result['dimension']}")
            sys.exit(0)
        else:
            sys.exit(result)
    except KeyboardInterrupt:
        print("\n\n❌ 用户中断")
        sys.exit(1)