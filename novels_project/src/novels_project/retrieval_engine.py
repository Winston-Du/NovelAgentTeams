"""
样例检索引擎 - 基于 Chroma 的向量库
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
    """样例检索引擎"""

    def __init__(self,
                 sample_dir: str = "samples",
                 persist_dir: str = "vector_db/chroma_data"):
        """
        初始化样例检索引擎

        Args:
            sample_dir: 样例文件目录
            persist_dir: 向量库持久化目录
        """
        self.sample_dir = Path(sample_dir)
        self.persist_dir = Path(persist_dir)

        # 配置 Embedding API
        api_key = os.getenv("COMPANY_API_KEY")
        api_base = os.getenv(
            "EMBEDDING_API_BASE_URL",
            "http://ai-service.tal.com/openai-compatible/v1"
        )

        if not api_key:
            raise ValueError("COMPANY_API_KEY 环境变量未设置")

        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-v4",
            base_url=api_base,
            api_key=api_key,
            #dimensions=1024  # 如果API支持的话
        )

        self.vectorstore = None
        self._initialize_vectorstore()

    def _initialize_vectorstore(self):
        """初始化或加载已有的向量库"""
        if self.persist_dir.exists() and any(self.persist_dir.iterdir()):
            # 加载已有向量库
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
            # 首次初始化，构建向量库
            self._build_vectorstore()

    def _build_vectorstore(self):
        """构建向量库（带重试机制）"""
        if not self.sample_dir.exists():
            print(f"⚠️  样例目录 {self.sample_dir} 不存在，跳过向量库构建")
            return

        print("🔨 构建向量库中...")

        # 创建重试处理器（最多重试3次）
        retry_handler = RateLimitHandler(max_retries=3, base_delay=2.0)

        # 包装构建逻辑，添加重试
        @retry_handler.retry_on_rate_limit
        def build_with_retry():
            # 加载所有 Markdown 文件
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

            # 分割文本（增大chunk_size减少embedding调用次数）
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,  # 从500增加到1000，减少chunk数量
                chunk_overlap=100
            )
            splits = splitter.split_documents(docs)

            print(f"📝 分割成 {len(splits)} 个文档块")

            # 如果文档块太多，批量处理以避免速率限制
            if len(splits) > 10:
                print(f"⚠️  文档块较多 ({len(splits)}个)，将分批处理以避免速率限制...")
                return self._build_vectorstore_in_batches(splits)
            else:
                # 创建向量库（这会调用embedding API）
                print("正在调用 Embedding API 生成向量...")
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

            # 检查是否是配额限制
            if "429" in error_msg or "quota" in error_msg.lower():
                print("   原因：Embedding API 配额已耗尽，重试也失败")
                print("   ℹ️  系统将以降级模式运行（无样例检索）")
                print("   ℹ️  这不影响核心创作功能，Agent 将依赖 Prompt 模板进行创作")
            else:
                print("   样例检索功能将不可用")

            print(f"   提示：您可以继续运行 'python run.py --chapter 1' 进行创作")

    def _build_vectorstore_in_batches(self, splits: List, batch_size: int = 5):
        """
        分批构建向量库，避免速率限制

        Args:
            splits: 文档块列表
            batch_size: 每批处理的文档数

        Returns:
            Chroma 向量库实例
        """
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
                    # 第一批：创建新的向量库
                    vectorstore = Chroma.from_documents(
                        documents=batch,
                        embedding=self.embeddings,
                        persist_directory=str(self.persist_dir)
                    )
                else:
                    # 后续批次：添加到已有向量库
                    vectorstore.add_documents(batch)

                # 每批之间添加延迟，避免速率限制
                if i + batch_size < len(splits):
                    delay = 2.0  # 批次之间等待2秒
                    print(f"   等待 {delay} 秒以避免速率限制...")
                    time.sleep(delay)

            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    print(f"   批次 {batch_num} 遇到速率限制")
                    # 重试处理器会自动处理
                    raise
                else:
                    raise

        print(f"✅ 向量库分批构建完成 ({len(splits)} 个文档块)")
        return vectorstore

    def retrieve_samples(self,
                        query: str,
                        k: int = 3,
                        chapter_type: Optional[str] = None) -> List[str]:
        """
        检索相似样例

        Args:
            query: 查询描述
            k: 返回的样例数
            chapter_type: 可选，限制搜索范围

        Returns:
            相似样例列表
        """
        if not self.vectorstore:
            return ["⚠️  向量库未初始化，无法检索样例"]

        try:
            # 执行相似度搜索
            results = self.vectorstore.similarity_search(query, k=k)

            if not results:
                return ["未找到相关样例"]

            # 格式化输出
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
        """刷新向量库（当样例目录有新文件时调用）"""
        import shutil
        if self.persist_dir.exists():
            shutil.rmtree(self.persist_dir)
        self._build_vectorstore()
        print("✅ 向量库已刷新")


# 全局实例（可选）
_global_engine = None

def get_retrieval_engine() -> SampleRetrievalEngine:
    """获取全局检索引擎实例"""
    global _global_engine
    if _global_engine is None:
        _global_engine = SampleRetrievalEngine()
    return _global_engine
