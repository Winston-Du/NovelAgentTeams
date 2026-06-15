"""
单元测试：retrieval_engine 模块测试

测试范围：
1. SampleRetrievalEngine.__init__（默认/自定义参数、不同模型）
2. SILICONFLOW_MODELS 字典查找
3. _ensure_initialized（已初始化/无API Key/有API Key/初始化失败）
4. _initialize_vectorstore（persist_dir存在/不存在）
5. _build_vectorstore（sample_dir不存在/无md文件/embeddings未初始化/成功构建）
6. retrieve_samples（vectorstore未初始化/成功检索/空结果/异常）
7. refresh（成功刷新）
8. get_retrieval_engine（首次创建/二次返回相同/自定义参数/None参数使用project_config）
"""

import sys
import os
from unittest.mock import MagicMock, patch, PropertyMock, Mock, call
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Mock ALL external langchain dependencies in sys.modules BEFORE importing
# the module under test. This ensures the module-level try/except succeeds.
# After import, we patch the module's local references directly.
# ---------------------------------------------------------------------------

_mock_langchain_openai = MagicMock()
_mock_langchain_community = MagicMock()
_mock_langchain_community_document_loaders = MagicMock()
_mock_langchain_text_splitters = MagicMock()
_mock_langchain_community_vectorstores = MagicMock()

sys.modules['langchain_openai'] = _mock_langchain_openai
sys.modules['langchain_community'] = _mock_langchain_community
sys.modules['langchain_community.document_loaders'] = _mock_langchain_community_document_loaders
sys.modules['langchain_text_splitters'] = _mock_langchain_text_splitters
sys.modules['langchain_community.vectorstores'] = _mock_langchain_community_vectorstores

from novels_project.retrieval_engine import SampleRetrievalEngine, get_retrieval_engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_global_engine():
    """Ensure _global_engine is reset between tests."""
    import novels_project.retrieval_engine as re_mod
    re_mod._global_engine = None
    yield
    re_mod._global_engine = None


# ---------------------------------------------------------------------------
# SampleRetrievalEngine.__init__
# ---------------------------------------------------------------------------

class TestSampleRetrievalEngineInit:
    """测试 SampleRetrievalEngine.__init__"""

    def test_init_default_params(self):
        engine = SampleRetrievalEngine()
        assert engine.sample_dir == Path("samples")
        assert engine.persist_dir == Path("vector_db/chroma_data")
        assert engine.embedding_model_name == "BAAI/bge-large-zh-v1.5"
        assert engine.max_tokens == 512
        assert engine.chunk_size == 400
        assert engine.vectorstore is None
        assert engine._initialized is False

    def test_init_custom_params(self):
        engine = SampleRetrievalEngine(
            sample_dir="custom_samples",
            persist_dir="custom_db",
            embedding_model="bge-m3",
        )
        assert engine.sample_dir == Path("custom_samples")
        assert engine.persist_dir == Path("custom_db")
        assert engine.embedding_model_name == "BAAI/bge-m3"
        assert engine.max_tokens == 8192
        assert engine.chunk_size == 6000

    def test_init_different_embedding_model_qwen3_8b(self):
        engine = SampleRetrievalEngine(embedding_model="qwen3-embedding-8b")
        assert engine.embedding_model_name == "Qwen/Qwen3-Embedding-8B"
        assert engine.max_tokens == 32768
        assert engine.chunk_size == 24000

    def test_init_different_embedding_model_bge_large_en(self):
        engine = SampleRetrievalEngine(embedding_model="bge-large-en")
        assert engine.embedding_model_name == "BAAI/bge-large-en-v1.5"
        assert engine.max_tokens == 512
        assert engine.chunk_size == 400

    def test_init_unknown_model_falls_back_to_name_as_model(self):
        """Unknown model name uses the name itself as API model name."""
        engine = SampleRetrievalEngine(embedding_model="unknown-model")
        assert engine.embedding_model_name == "unknown-model"
        assert engine.max_tokens == 512  # default fallback
        assert engine.chunk_size == 400


# ---------------------------------------------------------------------------
# SILICONFLOW_MODELS
# ---------------------------------------------------------------------------

class TestSiliconflowModels:
    """测试 SILICONFLOW_MODELS 字典"""

    def test_dict_contains_bge_large_zh(self):
        model_info = SampleRetrievalEngine.SILICONFLOW_MODELS['bge-large-zh']
        assert model_info[0] == 'BAAI/bge-large-zh-v1.5'
        assert model_info[1] == 512
        assert model_info[2] == 400

    def test_dict_contains_bge_m3(self):
        model_info = SampleRetrievalEngine.SILICONFLOW_MODELS['bge-m3']
        assert model_info[0] == 'BAAI/bge-m3'
        assert model_info[1] == 8192
        assert model_info[2] == 6000

    def test_dict_contains_bge_m3_pro(self):
        model_info = SampleRetrievalEngine.SILICONFLOW_MODELS['bge-m3-pro']
        assert model_info[0] == 'Pro/BAAI/bge-m3'

    def test_dict_contains_qwen3_embedding_8b(self):
        model_info = SampleRetrievalEngine.SILICONFLOW_MODELS['qwen3-embedding-8b']
        assert model_info[0] == 'Qwen/Qwen3-Embedding-8B'
        assert model_info[2] == 24000

    def test_dict_contains_qwen3_embedding_0_6b(self):
        model_info = SampleRetrievalEngine.SILICONFLOW_MODELS['qwen3-embedding-0.6b']
        assert model_info[0] == 'Qwen/Qwen3-Embedding-0.6B'

    def test_dict_has_7_entries(self):
        assert len(SampleRetrievalEngine.SILICONFLOW_MODELS) == 7


# ---------------------------------------------------------------------------
# _ensure_initialized
# ---------------------------------------------------------------------------

class TestEnsureInitialized:
    """测试 _ensure_initialized"""

    RE_MOD = 'novels_project.retrieval_engine'

    def test_already_initialized_does_nothing(self):
        with patch(f'{self.RE_MOD}.OpenAIEmbeddings') as mock_oe:
            engine = SampleRetrievalEngine()
            engine._initialized = True
            engine._ensure_initialized()
            mock_oe.assert_not_called()

    def test_no_api_key_returns_early(self, monkeypatch):
        monkeypatch.delenv("siliconflow_api", raising=False)
        monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
        monkeypatch.delenv("siliconflow_api_key", raising=False)

        with patch(f'{self.RE_MOD}.OpenAIEmbeddings') as mock_oe:
            engine = SampleRetrievalEngine()
            engine._ensure_initialized()
            assert engine._initialized is False
            mock_oe.assert_not_called()

    def test_api_key_exists_initializes_embeddings(self, monkeypatch):
        monkeypatch.delenv("siliconflow_api", raising=False)
        monkeypatch.delenv("siliconflow_api_key", raising=False)
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-api-key")
        mock_embeddings_instance = MagicMock()

        with patch(f'{self.RE_MOD}.OpenAIEmbeddings') as mock_oe:
            mock_oe.return_value = mock_embeddings_instance
            engine = SampleRetrievalEngine()
            with patch.object(engine, '_initialize_vectorstore'):
                engine._ensure_initialized()

            mock_oe.assert_called_once_with(
                model="BAAI/bge-large-zh-v1.5",
                base_url="https://api.siliconflow.cn/v1",
                api_key="test-api-key",
            )
            assert engine.embeddings is mock_embeddings_instance
            assert engine._initialized is True

    def test_api_key_from_siliconflow_api_env(self, monkeypatch):
        monkeypatch.setenv("siliconflow_api", "key-from-siliconflow-api")
        monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
        monkeypatch.delenv("siliconflow_api_key", raising=False)

        with patch(f'{self.RE_MOD}.OpenAIEmbeddings') as mock_oe:
            mock_oe.return_value = MagicMock()
            engine = SampleRetrievalEngine()
            with patch.object(engine, '_initialize_vectorstore'):
                engine._ensure_initialized()

            call_kwargs = mock_oe.call_args[1]
            assert call_kwargs["api_key"] == "key-from-siliconflow-api"

    def test_api_key_from_lowercase_env(self, monkeypatch):
        monkeypatch.delenv("siliconflow_api", raising=False)
        monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)
        monkeypatch.setenv("siliconflow_api_key", "lowercase-key")

        with patch(f'{self.RE_MOD}.OpenAIEmbeddings') as mock_oe:
            mock_oe.return_value = MagicMock()
            engine = SampleRetrievalEngine()
            with patch.object(engine, '_initialize_vectorstore'):
                engine._ensure_initialized()

            call_kwargs = mock_oe.call_args[1]
            assert call_kwargs["api_key"] == "lowercase-key"

    def test_embedding_init_fails_returns_early(self, monkeypatch):
        monkeypatch.setenv("SILICONFLOW_API_KEY", "test-key")

        with patch(f'{self.RE_MOD}.OpenAIEmbeddings') as mock_oe:
            mock_oe.side_effect = RuntimeError("Connection refused")
            engine = SampleRetrievalEngine()
            engine._ensure_initialized()
            assert engine._initialized is False
            mock_oe.assert_called_once()


# ---------------------------------------------------------------------------
# _initialize_vectorstore
# ---------------------------------------------------------------------------

class TestInitializeVectorstore:
    """测试 _initialize_vectorstore"""

    RE_MOD = 'novels_project.retrieval_engine'

    def test_persist_dir_exists_and_populated(self):
        mock_chroma_instance = MagicMock()
        mock_chroma_instance._collection.count.return_value = 42

        with patch(f'{self.RE_MOD}.Chroma') as mock_chroma:
            mock_chroma.return_value = mock_chroma_instance
            engine = SampleRetrievalEngine(persist_dir="test_db")
            engine.embeddings = MagicMock()

            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'iterdir', return_value=[Path("file1")]):
                    engine._initialize_vectorstore()

            mock_chroma.assert_called_once_with(
                persist_directory="test_db",
                embedding_function=engine.embeddings,
            )
            assert engine.vectorstore is mock_chroma_instance

    def test_persist_dir_does_not_exist_builds_new(self):
        engine = SampleRetrievalEngine(persist_dir="nonexistent")
        engine.embeddings = MagicMock()

        with patch.object(engine, '_build_vectorstore') as mock_build:
            with patch.object(Path, 'exists', return_value=False):
                engine._initialize_vectorstore()

        mock_build.assert_called_once()

    def test_persist_dir_exists_but_empty_builds_new(self):
        engine = SampleRetrievalEngine(persist_dir="empty_db")
        engine.embeddings = MagicMock()

        with patch.object(engine, '_build_vectorstore') as mock_build:
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'iterdir', return_value=[]):
                    engine._initialize_vectorstore()

        mock_build.assert_called_once()

    def test_loading_existing_vectordb_fails_falls_back_to_build(self):
        with patch(f'{self.RE_MOD}.Chroma') as mock_chroma:
            mock_chroma.side_effect = RuntimeError("Corrupt database")
            engine = SampleRetrievalEngine(persist_dir="corrupt_db")
            engine.embeddings = MagicMock()

            with patch.object(engine, '_build_vectorstore') as mock_build:
                with patch.object(Path, 'exists', return_value=True):
                    with patch.object(Path, 'iterdir', return_value=[Path("f1")]):
                        engine._initialize_vectorstore()

            mock_build.assert_called_once()


# ---------------------------------------------------------------------------
# _build_vectorstore
# ---------------------------------------------------------------------------

class TestBuildVectorstore:
    """测试 _build_vectorstore"""

    RE_MOD = 'novels_project.retrieval_engine'

    def test_sample_dir_does_not_exist(self):
        engine = SampleRetrievalEngine(sample_dir="nonexistent_samples")
        engine.embeddings = MagicMock()

        with patch.object(Path, 'exists', return_value=False):
            engine._build_vectorstore()

        assert engine.vectorstore is None

    def test_no_markdown_files(self):
        engine = SampleRetrievalEngine(sample_dir="empty_samples")
        engine.embeddings = MagicMock()

        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'glob', return_value=[]):
                engine._build_vectorstore()

        assert engine.vectorstore is None

    def test_embeddings_not_initialized(self):
        engine = SampleRetrievalEngine(sample_dir="samples")
        # Don't set embeddings attribute

        with patch.object(Path, 'exists', return_value=True):
            mock_file = MagicMock()
            mock_file.__str__ = lambda s: "test.md"
            with patch.object(Path, 'glob', return_value=[mock_file]):
                engine._build_vectorstore()

        assert engine.vectorstore is None

    def test_embeddings_is_none(self):
        engine = SampleRetrievalEngine(sample_dir="samples")
        engine.embeddings = None

        with patch.object(Path, 'exists', return_value=True):
            mock_file = MagicMock()
            with patch.object(Path, 'glob', return_value=[mock_file]):
                engine._build_vectorstore()

        assert engine.vectorstore is None

    def test_successful_build_small_docs(self):
        engine = SampleRetrievalEngine(sample_dir="samples", persist_dir="db")
        engine.embeddings = MagicMock()

        mock_docs = [MagicMock(), MagicMock()]
        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = mock_docs

        mock_splits = [MagicMock() for _ in range(5)]
        mock_splitter_instance = MagicMock()
        mock_splitter_instance.split_documents.return_value = mock_splits

        mock_vectorstore = MagicMock()

        with patch(f'{self.RE_MOD}.DirectoryLoader') as mock_loader:
            mock_loader.return_value = mock_loader_instance
            with patch(f'{self.RE_MOD}.RecursiveCharacterTextSplitter') as mock_splitter:
                mock_splitter.return_value = mock_splitter_instance
                with patch(f'{self.RE_MOD}.Chroma') as mock_chroma:
                    mock_chroma.from_documents.return_value = mock_vectorstore

                    with patch.object(Path, 'exists', return_value=True):
                        mock_file = MagicMock()
                        with patch.object(Path, 'glob', return_value=[mock_file]):
                            engine._build_vectorstore()

        mock_loader.assert_called_once()
        mock_chroma.from_documents.assert_called_once()
        assert engine.vectorstore is mock_vectorstore

    def test_successful_build_large_docs_triggers_batching(self):
        engine = SampleRetrievalEngine(sample_dir="samples", persist_dir="db")
        engine.embeddings = MagicMock()

        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = [MagicMock()]

        mock_splits = [MagicMock() for _ in range(15)]
        mock_splitter_instance = MagicMock()
        mock_splitter_instance.split_documents.return_value = mock_splits

        mock_vectorstore = MagicMock()

        with patch(f'{self.RE_MOD}.DirectoryLoader') as mock_loader:
            mock_loader.return_value = mock_loader_instance
            with patch(f'{self.RE_MOD}.RecursiveCharacterTextSplitter') as mock_splitter:
                mock_splitter.return_value = mock_splitter_instance
                with patch(f'{self.RE_MOD}.Chroma') as mock_chroma:
                    mock_chroma.from_documents.return_value = mock_vectorstore

                    with patch.object(Path, 'exists', return_value=True):
                        mock_file = MagicMock()
                        with patch.object(Path, 'glob', return_value=[mock_file]):
                            with patch('time.sleep'):
                                engine._build_vectorstore()

        assert mock_chroma.from_documents.call_count >= 1

    def test_build_raises_exception_is_handled(self):
        engine = SampleRetrievalEngine(sample_dir="samples")
        engine.embeddings = MagicMock()

        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = [MagicMock()]

        mock_splitter_instance = MagicMock()
        mock_splitter_instance.split_documents.return_value = [MagicMock()]

        with patch(f'{self.RE_MOD}.DirectoryLoader') as mock_loader:
            mock_loader.return_value = mock_loader_instance
            with patch(f'{self.RE_MOD}.RecursiveCharacterTextSplitter') as mock_splitter:
                mock_splitter.return_value = mock_splitter_instance
                with patch(f'{self.RE_MOD}.Chroma') as mock_chroma:
                    mock_chroma.from_documents.side_effect = RuntimeError("API Error")

                    with patch.object(Path, 'exists', return_value=True):
                        mock_file = MagicMock()
                        with patch.object(Path, 'glob', return_value=[mock_file]):
                            engine._build_vectorstore()

        assert engine.vectorstore is None

    def test_build_vectorstore_sets_chunk_size_based_on_model(self):
        engine = SampleRetrievalEngine(embedding_model="bge-m3")
        engine.embeddings = MagicMock()

        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = [MagicMock()]

        mock_splitter_instance = MagicMock()
        mock_splitter_instance.split_documents.return_value = [MagicMock()]

        with patch(f'{self.RE_MOD}.DirectoryLoader') as mock_loader:
            mock_loader.return_value = mock_loader_instance
            with patch(f'{self.RE_MOD}.RecursiveCharacterTextSplitter') as mock_splitter:
                mock_splitter.return_value = mock_splitter_instance
                with patch(f'{self.RE_MOD}.Chroma') as mock_chroma:
                    mock_chroma.from_documents.return_value = MagicMock()

                    with patch.object(Path, 'exists', return_value=True):
                        with patch.object(Path, 'glob', return_value=[MagicMock()]):
                            engine._build_vectorstore()

        call_kwargs = mock_splitter.call_args[1]
        assert call_kwargs["chunk_size"] == 4800  # int(6000 * 0.8)
        assert call_kwargs["chunk_overlap"] == 50


# ---------------------------------------------------------------------------
# _build_vectorstore_in_batches
# ---------------------------------------------------------------------------

class TestBuildVectorstoreInBatches:
    """测试 _build_vectorstore_in_batches"""

    RE_MOD = 'novels_project.retrieval_engine'

    def test_builds_in_batches(self):
        with patch(f'{self.RE_MOD}.Chroma') as mock_chroma:
            engine = SampleRetrievalEngine(persist_dir="db")
            engine.embeddings = MagicMock()

            mock_splits = [MagicMock() for _ in range(7)]
            mock_vs = MagicMock()
            mock_chroma.from_documents.return_value = mock_vs

            with patch('time.sleep'):
                result = engine._build_vectorstore_in_batches(mock_splits, batch_size=3)

            assert mock_chroma.from_documents.call_count == 1
            assert mock_vs.add_documents.call_count == 2
            assert result is mock_vs

    def test_handles_rate_limit_retry_in_batch(self):
        with patch(f'{self.RE_MOD}.Chroma') as mock_chroma:
            engine = SampleRetrievalEngine(persist_dir="db")
            engine.embeddings = MagicMock()

            mock_splits = [MagicMock() for _ in range(4)]
            mock_vs = MagicMock()

            call_count = [0]

            def from_documents_side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_vs
                else:
                    raise Exception("429 rate limit exceeded")

            mock_chroma.from_documents.side_effect = from_documents_side_effect
            mock_vs.add_documents.side_effect = lambda *a, **kw: None

            with patch('time.sleep'):
                result = engine._build_vectorstore_in_batches(mock_splits, batch_size=2)

            assert result is mock_vs


# ---------------------------------------------------------------------------
# retrieve_samples
# ---------------------------------------------------------------------------

class TestRetrieveSamples:
    """测试 retrieve_samples"""

    def test_vectorstore_not_initialized(self):
        engine = SampleRetrievalEngine()
        engine._initialized = True
        engine.vectorstore = None

        results = engine.retrieve_samples("test query")
        assert len(results) == 1
        assert "向量库未初始化" in results[0]

    def test_successful_retrieval(self):
        engine = SampleRetrievalEngine()
        engine._initialized = True
        engine.vectorstore = MagicMock()

        mock_doc1 = MagicMock()
        mock_doc1.metadata = {"source": "chapter1.md"}
        mock_doc1.page_content = "This is the content of chapter 1. " * 50
        mock_doc2 = MagicMock()
        mock_doc2.metadata = {"source": "chapter2.md"}
        mock_doc2.page_content = "Content of chapter 2. "

        engine.vectorstore.similarity_search.return_value = [mock_doc1, mock_doc2]

        results = engine.retrieve_samples("test query", k=2)

        assert len(results) == 2
        engine.vectorstore.similarity_search.assert_called_once_with("test query", k=2)
        assert "chapter1.md" in results[0]
        assert "chapter2.md" in results[1]
        assert "【样例 1】" in results[0]
        assert "【样例 2】" in results[1]

    def test_empty_results(self):
        engine = SampleRetrievalEngine()
        engine._initialized = True
        engine.vectorstore = MagicMock()
        engine.vectorstore.similarity_search.return_value = []

        results = engine.retrieve_samples("unrelated query")
        assert len(results) == 1
        assert results[0] == "未找到相关样例"

    def test_exception_returns_error_message(self):
        engine = SampleRetrievalEngine()
        engine._initialized = True
        engine.vectorstore = MagicMock()
        engine.vectorstore.similarity_search.side_effect = RuntimeError("DB error")

        results = engine.retrieve_samples("test")
        assert len(results) == 1
        assert "检索失败" in results[0]
        assert "DB error" in results[0]

    def test_calls_ensure_initialized(self):
        engine = SampleRetrievalEngine()
        engine.vectorstore = MagicMock()
        engine.vectorstore.similarity_search.return_value = []

        with patch.object(engine, '_ensure_initialized') as mock_ensure:
            engine.retrieve_samples("test")
        mock_ensure.assert_called_once()


# ---------------------------------------------------------------------------
# refresh
# ---------------------------------------------------------------------------

class TestRefresh:
    """测试 refresh"""

    def test_successful_refresh(self):
        engine = SampleRetrievalEngine(persist_dir="db")
        engine.embeddings = MagicMock()

        with patch.object(engine, '_ensure_initialized') as mock_ensure:
            with patch.object(Path, 'exists', return_value=True):
                with patch('shutil.rmtree') as mock_rmtree:
                    with patch.object(engine, '_build_vectorstore') as mock_build:
                        engine.refresh()

        mock_ensure.assert_called_once()
        mock_rmtree.assert_called_once_with(Path("db"))
        mock_build.assert_called_once()

    def test_refresh_when_persist_dir_not_exists(self):
        engine = SampleRetrievalEngine(persist_dir="no_db")
        engine.embeddings = MagicMock()

        with patch.object(engine, '_ensure_initialized'):
            with patch.object(Path, 'exists', return_value=False):
                with patch('shutil.rmtree') as mock_rmtree:
                    with patch.object(engine, '_build_vectorstore') as mock_build:
                        engine.refresh()

        mock_rmtree.assert_not_called()
        mock_build.assert_called_once()


# ---------------------------------------------------------------------------
# get_retrieval_engine
# ---------------------------------------------------------------------------

class TestGetRetrievalEngine:
    """测试 get_retrieval_engine 全局工厂函数"""

    PC = 'novels_project.project_config'

    def test_first_call_creates_engine(self, reset_global_engine):
        import novels_project.retrieval_engine as re_mod
        re_mod._global_engine = None

        with patch(f'{self.PC}.get_samples_dir', return_value=Path("/fake/samples")):
            with patch(f'{self.PC}.get_vector_db_dir', return_value=Path("/fake/vector_db")):
                engine = get_retrieval_engine()

        assert engine is not None
        assert isinstance(engine, SampleRetrievalEngine)
        assert re_mod._global_engine is engine

    def test_second_call_returns_same(self, reset_global_engine):
        import novels_project.retrieval_engine as re_mod
        re_mod._global_engine = None

        with patch(f'{self.PC}.get_samples_dir', return_value=Path("/fake/samples")):
            with patch(f'{self.PC}.get_vector_db_dir', return_value=Path("/fake/vector_db")):
                engine1 = get_retrieval_engine()
                engine2 = get_retrieval_engine()

        assert engine1 is engine2

    def test_with_custom_params(self, reset_global_engine):
        import novels_project.retrieval_engine as re_mod
        re_mod._global_engine = None

        engine = get_retrieval_engine(
            sample_dir="my_samples",
            persist_dir="my_db",
            embedding_model="bge-m3",
        )

        assert engine.sample_dir == Path("my_samples")
        assert engine.persist_dir == Path("my_db")
        assert engine.embedding_model_name == "BAAI/bge-m3"

    def test_with_none_params_uses_project_config(self, reset_global_engine):
        import novels_project.retrieval_engine as re_mod
        re_mod._global_engine = None

        with patch(f'{self.PC}.get_samples_dir', return_value=Path("/proj/samples")):
            with patch(f'{self.PC}.get_vector_db_dir', return_value=Path("/proj/vdb")):
                engine = get_retrieval_engine(sample_dir=None, persist_dir=None)

        assert engine.sample_dir == Path("/proj/samples")
        assert engine.persist_dir == Path("/proj/vdb/chroma_data")

    def test_custom_params_dont_affect_second_call(self, reset_global_engine):
        import novels_project.retrieval_engine as re_mod
        re_mod._global_engine = None

        with patch(f'{self.PC}.get_samples_dir', return_value=Path("/fake/s")):
            with patch(f'{self.PC}.get_vector_db_dir', return_value=Path("/fake/v")):
                e1 = get_retrieval_engine(sample_dir="first")
                e2 = get_retrieval_engine(sample_dir="second")

        assert e1 is e2
        assert e1.sample_dir == Path("first")


# ---------------------------------------------------------------------------
# Module-level ImportError branch (lines 21-25)
# ---------------------------------------------------------------------------

class TestImportErrorBranch:
    """Test the except ImportError branch by reloading the module with failed imports."""

    def test_import_error_sets_langchain_unavailable(self):
        """Simulate ImportError at module load time."""
        import importlib
        import novels_project.retrieval_engine as re_mod

        # Save original modules
        saved = {}
        for mod_name in ['langchain_openai', 'langchain_community', 'langchain_text_splitters',
                         'langchain_community.document_loaders', 'langchain_community.vectorstores']:
            saved[mod_name] = sys.modules.get(mod_name)

        try:
            # Remove modules to force ImportError
            for mod_name in saved:
                sys.modules[mod_name] = None

            # Now reload should fail the import
            importlib.reload(re_mod)
            # LANGCHAIN_AVAILABLE should be False
            assert re_mod.LANGCHAIN_AVAILABLE is False
        finally:
            # Restore
            for mod_name, mod in saved.items():
                if mod is not None:
                    sys.modules[mod_name] = mod
                elif mod_name in sys.modules:
                    del sys.modules[mod_name]

            # Re-reload to restore working state
            importlib.reload(re_mod)


# ---------------------------------------------------------------------------
# _build_vectorstore - empty docs returned (line 153)
# ---------------------------------------------------------------------------

class TestBuildVectorstoreEmptyDocs:
    """Test _build_vectorstore when loader returns empty docs."""

    RE_MOD = 'novels_project.retrieval_engine'

    def test_loader_returns_empty_docs(self):
        """DirectoryLoader.load() returns empty list -> early return None."""
        engine = SampleRetrievalEngine(sample_dir="samples")
        engine.embeddings = MagicMock()

        mock_loader_instance = MagicMock()
        mock_loader_instance.load.return_value = []

        with patch(f'{self.RE_MOD}.DirectoryLoader') as mock_loader:
            mock_loader.return_value = mock_loader_instance
            with patch.object(Path, 'exists', return_value=True):
                mock_file = MagicMock()
                with patch.object(Path, 'glob', return_value=[mock_file]):
                    engine._build_vectorstore()

        assert engine.vectorstore is None


# ---------------------------------------------------------------------------
# _build_vectorstore_in_batches - rate limit handling (lines 221-239)
# ---------------------------------------------------------------------------

class TestBuildVectorstoreInBatchesRateLimit:
    """Test rate-limit retry logic in _build_vectorstore_in_batches."""

    RE_MOD = 'novels_project.retrieval_engine'

    def test_429_retry_first_batch(self):
        """First batch hits 429 -> retries successfully."""
        with patch(f'{self.RE_MOD}.Chroma') as mock_chroma:
            engine = SampleRetrievalEngine(persist_dir="db")
            engine.embeddings = MagicMock()

            mock_splits = [MagicMock() for _ in range(4)]
            mock_vs = MagicMock()

            call_count = [0]

            def from_documents_side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise Exception("429 rate limit exceeded")
                return mock_vs

            mock_chroma.from_documents.side_effect = from_documents_side_effect

            with patch('time.sleep'):
                result = engine._build_vectorstore_in_batches(mock_splits, batch_size=2)

            assert result is mock_vs

    def test_non_rate_limit_error_raises(self):
        """Non-rate-limit error should propagate."""
        with patch(f'{self.RE_MOD}.Chroma') as mock_chroma:
            engine = SampleRetrievalEngine(persist_dir="db")
            engine.embeddings = MagicMock()

            mock_splits = [MagicMock() for _ in range(4)]
            mock_vs = MagicMock()
            mock_chroma.from_documents.return_value = mock_vs
            mock_vs.add_documents.side_effect = RuntimeError("Other error")

            with patch('time.sleep'):
                with pytest.raises(RuntimeError, match="Other error"):
                    engine._build_vectorstore_in_batches(mock_splits, batch_size=2)

    def test_rate_limit_retry_fails_then_raises(self):
        """Rate limit retry also fails -> raises."""
        with patch(f'{self.RE_MOD}.Chroma') as mock_chroma:
            engine = SampleRetrievalEngine(persist_dir="db")
            engine.embeddings = MagicMock()

            mock_splits = [MagicMock() for _ in range(4)]
            mock_vs = MagicMock()

            call_count = [0]

            def from_documents_side_effect(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_vs
                raise Exception("429 rate limit exceeded")

            mock_chroma.from_documents.side_effect = from_documents_side_effect
            mock_vs.add_documents.side_effect = Exception("429 rate limit exceeded")

            with patch('time.sleep'):
                with pytest.raises(Exception):
                    engine._build_vectorstore_in_batches(mock_splits, batch_size=2)