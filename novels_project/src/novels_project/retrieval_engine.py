"""
样例检索引擎 - 基于 Chroma 的向量库
使用 SiliconFlow Embedding API
"""
from pathlib import Path
from typing import List, Optional
import os
import time
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    from langchain_openai import OpenAIEmbeddings
    from langchain_community.document_loaders import DirectoryLoader, UnstructuredMarkdownLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_community.vectorstores import Chroma
    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    LANGCHAIN_AVAILABLE = False
    print("⚠️  警告：LangChain 相关包未安装")
    print(f"请运行：pip install langchain chromadb langchain-community langchain-openai langchain-text-splitters")
    print(f"错误详情: {e}")

from .retry_handler import RateLimitHandler


class SampleRetrievalEngine:
    """样例检索引擎 - 使用 SiliconFlow Embedding API"""

    # SiliconFlow 支持的 Embedding 模型及其 token 限制
    SILICONFLOW_MODELS = {
        # 模型名: (API模型名, token限制, 建议chunk_size)
        'bge-large-zh': ('BAAI/bge-large-zh-v1.5', 512, 400),      # 中文
        'bge-large-en': ('BAAI/bge-large-en-v1.5', 512, 400),      # 英文
        'bge-m3': ('BAAI/bge-m3', 8192, 6000),                      # 多语言
        'bge-m3-pro': ('Pro/BAAI/bge-m3', 8192, 6000),             # 多语言增强版
        'qwen3-embedding-8b': ('Qwen/Qwen3-Embedding-8B', 32768, 24000),  # 大模型
        'qwen3-embedding-4b': ('Qwen/Qwen3-Embedding-4B', 32768, 24000),
        'qwen3-embedding-0.6b': ('Qwen/Qwen3-Embedding-0.6B', 32768, 24000),
    }

    def __init__(self,
                 sample_dir: str = "samples",
                 persist_dir: str = "vector_db/chroma_data",
                 embedding_model: str = 'bge-large-zh'):
        """
        初始化样例检索引擎

        Args:
            sample_dir: 样例文件目录
            persist_dir: 向量库持久化目录
            embedding_model: Embedding 模型名称
        """
        self.sample_dir = Path(sample_dir)
        self.persist_dir = Path(persist_dir)
        self.vectorstore = None
        self._initialized = False
        
        # 获取模型配置
        model_config = self.SILICONFLOW_MODELS.get(embedding_model, (embedding_model, 512, 400))
        self.embedding_model_name = model_config[0]
        self.max_tokens = model_config[1]
        self.chunk_size = model_config[2]

        print(f"📚 样例检索引擎已创建（延迟初始化）")
        print(f"   样例目录: {self.sample_dir}")
        print(f"   向量库目录: {self.persist_dir}")
        print(f"   Embedding 模型: {self.embedding_model_name}")
        print(f"   Token 限制: {self.max_tokens}, Chunk 大小: {self.chunk_size}")

    def _ensure_initialized(self):
        """确保向量库已初始化"""
        if self._initialized:
            return

        # 从环境变量获取 SiliconFlow API Key（支持多种命名方式）
        api_key = (
            os.getenv("siliconflow_api") or
            os.getenv("SILICONFLOW_API_KEY") or
            os.getenv("siliconflow_api_key")
        )
        
        if not api_key:
            print("⚠️  siliconflow_api 环境变量未设置，样例检索功能将不可用")
            print("   请设置环境变量: export siliconflow_api=your_api_key")
            return

        try:
            # SiliconFlow API 兼容 OpenAI 格式
            self.embeddings = OpenAIEmbeddings(
                model=self.embedding_model_name,
                base_url="https://api.siliconflow.cn/v1",
                api_key=api_key,
            )
            print(f"✅ Embeddings 初始化成功 (模型: {self.embedding_model_name})")
        except Exception as e:
            print(f"⚠️  Embedding 初始化失败: {e}")
            return

        self._initialize_vectorstore()
        self._initialized = True

    def _initialize_vectorstore(self):
        """初始化或加载已有的向量库"""
        if self.persist_dir.exists() and any(self.persist_dir.iterdir()):
            try:
                self.vectorstore = Chroma(
                    persist_directory=str(self.persist_dir),
                    embedding_function=self.embeddings
                )
                count = self.vectorstore._collection.count()
                print(f"✅ 向量库已加载，文档数: {count}")
            except Exception as e:
                print(f"⚠️  加载向量库失败: {e}")
                print("   将重新构建...")
                self._build_vectorstore()
        else:
            self._build_vectorstore()

    def _build_vectorstore(self):
        """构建向量库"""
        if not self.sample_dir.exists():
            print(f"⚠️  样例目录 {self.sample_dir} 不存在，跳过向量库构建")
            return

        sample_files = list(self.sample_dir.glob("**/*.md"))
        if not sample_files:
            print(f"⚠️  样例目录中没有 Markdown 文件，跳过向量库构建")
            return

        if not hasattr(self, 'embeddings') or self.embeddings is None:
            print(f"⚠️  Embeddings 未初始化，跳过向量库构建")
            return

        print("🔨 构建向量库中...")

        retry_handler = RateLimitHandler(max_retries=3, base_delay=2.0)

        @retry_handler.retry_on_rate_limit
        def build_with_retry():
            loader = DirectoryLoader(
                str(self.sample_dir),
                glob="**/*.md",
                loader_cls=UnstructuredMarkdownLoader,
                show_progress=True
            )
            docs = loader.load()

            if not docs:
                print("⚠️  未找到样例文件")
                return None

            print(f"📄 找到 {len(docs)} 个样例文件")

            # 使用根据模型配置的 chunk_size
            # chunk_size 设为 token 限制的 80% 左右，留出安全余量
            safe_chunk_size = int(self.chunk_size * 0.8)
            
            print(f"📝 使用 chunk_size: {safe_chunk_size} (安全余量 80%)")
            
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=safe_chunk_size,
                chunk_overlap=50  # 减少 overlap 以确保不超限
            )
            splits = splitter.split_documents(docs)

            print(f"📝 分割成 {len(splits)} 个文档块")

            if len(splits) > 10:
                print(f"⚠️  文档块较多，将分批处理...")
                return self._build_vectorstore_in_batches(splits)
            else:
                print("正在调用 SiliconFlow Embedding API 生成向量...")
                vectorstore = Chroma.from_documents(
                    documents=splits,
                    embedding=self.embeddings,
                    persist_directory=str(self.persist_dir)
                )
                print(f"✅ 向量库构建完成")
                return vectorstore

        try:
            self.vectorstore = build_with_retry()
        except Exception as e:
            error_msg = str(e)
            print(f"❌ 向量库构建失败: {error_msg}")

    def _build_vectorstore_in_batches(self, splits: List, batch_size: int = 3):
        """分批构建向量库"""
        import math

        total_batches = math.ceil(len(splits) / batch_size)
        print(f"分 {total_batches} 批处理，每批 {batch_size} 个文档块")

        vectorstore = None

        for i in range(0, len(splits), batch_size):
            batch_num = i // batch_size + 1
            batch = splits[i:i + batch_size]

            print(f"处理第 {batch_num}/{total_batches} 批 ({len(batch)} 个文档块)...")

            try:
                if vectorstore is None:
                    vectorstore = Chroma.from_documents(
                        documents=batch,
                        embedding=self.embeddings,
                        persist_directory=str(self.persist_dir)
                    )
                else:
                    vectorstore.add_documents(batch)

                if i + batch_size < len(splits):
                    delay = 1.0
                    print(f"   等待 {delay} 秒...")
                    time.sleep(delay)

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg or "rate" in error_msg.lower():
                    print(f"   批次 {batch_num} 遇到速率限制，等待后重试...")
                    time.sleep(3.0)
                    try:
                        if vectorstore is None:
                            vectorstore = Chroma.from_documents(
                                documents=batch,
                                embedding=self.embeddings,
                                persist_directory=str(self.persist_dir)
                            )
                        else:
                            vectorstore.add_documents(batch)
                    except Exception as e2:
                        print(f"   重试失败: {e2}")
                        raise
                else:
                    raise

        print(f"✅ 向量库分批构建完成 ({len(splits)} 个文档块)")
        return vectorstore

    def retrieve_samples(self,
                        query: str,
                        k: int = 3,
                        chapter_type: Optional[str] = None) -> List[str]:
        """检索相似样例"""
        self._ensure_initialized()

        if not self.vectorstore:
            return ["⚠️  向量库未初始化，无法检索样例。请先运行初始化脚本。"]

        try:
            results = self.vectorstore.similarity_search(query, k=k)

            if not results:
                return ["未找到相关样例"]

            formatted_results = []
            for i, doc in enumerate(results, 1):
                formatted_results.append(
                    f"【样例 {i}】\n"
                    f"来源: {doc.metadata.get('source', '未知')}\n"
                    f"内容摘录:\n{doc.page_content[:500]}...\n"
                )

            return formatted_results

        except Exception as e:
            return [f"❌ 检索失败: {e}"]

    def refresh(self):
        """刷新向量库"""
        self._ensure_initialized()
        import shutil
        if self.persist_dir.exists():
            shutil.rmtree(self.persist_dir)
        self._build_vectorstore()
        print("✅ 向量库已刷新")


# 全局实例
_global_engine = None

def get_retrieval_engine(
    sample_dir: Optional[str] = None,
    persist_dir: Optional[str] = None,
    embedding_model: str = 'bge-large-zh'
) -> SampleRetrievalEngine:
    """
    获取检索引擎实例。

    Args:
        sample_dir: 样例目录（可选，默认使用当前项目的 samples/）
        persist_dir: 向量库目录（可选，默认使用当前项目的 vector_db/）
        embedding_model: Embedding 模型名称
    """
    global _global_engine

    from .project_config import get_samples_dir, get_vector_db_dir

    if sample_dir is None:
        sample_dir = str(get_samples_dir())
    if persist_dir is None:
        persist_dir = str(get_vector_db_dir() / "chroma_data")

    if _global_engine is None:
        _global_engine = SampleRetrievalEngine(
            sample_dir=sample_dir,
            persist_dir=persist_dir,
            embedding_model=embedding_model,
        )
    return _global_engine
