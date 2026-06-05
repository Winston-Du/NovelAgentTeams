"""
单元测试：样例检索工具 (sample_retriever)

测试覆盖:
- retrieve_writing_samples, refresh_sample_library
"""
import pytest
from unittest.mock import patch, MagicMock


# =========================================================================
#  retrieve_writing_samples
# =========================================================================
class TestRetrieveWritingSamples:
    """Tests for retrieve_writing_samples."""

    def _mock_engine(self, samples=None, side_effect=None):
        """Create a mocked retrieval engine."""
        mock = MagicMock()
        if side_effect:
            mock.retrieve_samples.side_effect = side_effect
        elif samples is not None:
            mock.retrieve_samples.return_value = samples
        else:
            mock.retrieve_samples.return_value = []
        return mock

    def _patch_engine(self, mock_engine):
        """Set up the mock engine chain."""
        def mock_get_engine():
            return mock_engine

        # We need to reset the _engine global in the module before each test
        import novels_project.tools.sample_retriever as sr_mod
        sr_mod._engine = None

        return patch.object(sr_mod, "get_engine", side_effect=mock_get_engine)

    def test_success(self):
        """retrieve_writing_samples returns formatted results."""
        import novels_project.tools.sample_retriever as sr_mod

        mock_engine = self._mock_engine(samples=["【样例 1】\n来源: test.md\n内容摘录:\n测试内容..."])
        sr_mod._engine = None

        with patch.object(sr_mod, "get_engine", return_value=mock_engine):
            result = sr_mod.retrieve_writing_samples(
                query="权谋听证",
                chapter_type="权谋章",
                num_samples=3,
            )

            mock_engine.retrieve_samples.assert_called_once_with(
                query="权谋听证",
                k=3,
                chapter_type="权谋章",
            )
            assert "找到" in result
            assert "样例" in result

    def test_empty_results(self):
        """retrieve_writing_samples returns not-found message when no samples."""
        import novels_project.tools.sample_retriever as sr_mod

        mock_engine = self._mock_engine(samples=[])
        sr_mod._engine = None

        with patch.object(sr_mod, "get_engine", return_value=mock_engine):
            result = sr_mod.retrieve_writing_samples(
                query="不存在的查询",
                num_samples=3,
            )
            assert "未找到" in result

    def test_exception(self):
        """retrieve_writing_samples handles exceptions gracefully."""
        import novels_project.tools.sample_retriever as sr_mod

        mock_engine = self._mock_engine(
            side_effect=RuntimeError("Connection failed")
        )
        sr_mod._engine = None

        with patch.object(sr_mod, "get_engine", return_value=mock_engine):
            result = sr_mod.retrieve_writing_samples(
                query="测试",
                num_samples=3,
            )
            assert "样例检索失败" in result

    def test_without_chapter_type(self):
        """retrieve_writing_samples without chapter_type."""
        import novels_project.tools.sample_retriever as sr_mod

        mock_engine = self._mock_engine(samples=["sample1", "sample2"])
        sr_mod._engine = None

        with patch.object(sr_mod, "get_engine", return_value=mock_engine):
            result = sr_mod.retrieve_writing_samples(
                query="战斗场景",
                num_samples=2,
            )

            mock_engine.retrieve_samples.assert_called_once_with(
                query="战斗场景",
                k=2,
                chapter_type=None,
            )
            assert "找到" in result

    def test_default_num_samples(self):
        """retrieve_writing_samples uses default num_samples=3."""
        import novels_project.tools.sample_retriever as sr_mod

        mock_engine = self._mock_engine(samples=["s1", "s2", "s3"])
        sr_mod._engine = None

        with patch.object(sr_mod, "get_engine", return_value=mock_engine):
            result = sr_mod.retrieve_writing_samples(query="测试默认参数")

            mock_engine.retrieve_samples.assert_called_once_with(
                query="测试默认参数",
                k=3,
                chapter_type=None,
            )
            assert "找到 3" in result

    def test_returns_no_samples_message(self):
        """retrieve_writing_samples returns the emoji message for no samples."""
        import novels_project.tools.sample_retriever as sr_mod

        mock_engine = self._mock_engine(samples=[])
        sr_mod._engine = None

        with patch.object(sr_mod, "get_engine", return_value=mock_engine):
            result = sr_mod.retrieve_writing_samples(query="测试")
            assert "❌" in result


# =========================================================================
#  refresh_sample_library
# =========================================================================
class TestRefreshSampleLibrary:
    """Tests for refresh_sample_library."""

    def test_success(self):
        """refresh_sample_library refreshes the vector store."""
        import novels_project.tools.sample_retriever as sr_mod

        mock_engine = MagicMock()
        sr_mod._engine = None

        with patch.object(sr_mod, "get_engine", return_value=mock_engine):
            result = sr_mod.refresh_sample_library()

            mock_engine.refresh.assert_called_once()
            assert "样例库已刷新" in result


# =========================================================================
#  get_engine
# =========================================================================
class TestGetEngine:
    """Tests for get_engine (internal helper)."""

    def test_creates_engine_on_first_call(self):
        """get_engine creates and caches the engine on first call."""
        import novels_project.tools.sample_retriever as sr_mod

        sr_mod._engine = None
        mock_engine = MagicMock()

        with patch("novels_project.retrieval_engine.get_retrieval_engine",
                   return_value=mock_engine):
            result = sr_mod.get_engine()

            assert result is mock_engine
            assert sr_mod._engine is mock_engine

    def test_returns_cached_engine(self):
        """get_engine returns cached engine on subsequent calls."""
        import novels_project.tools.sample_retriever as sr_mod

        mock_engine = MagicMock()
        sr_mod._engine = mock_engine

        result = sr_mod.get_engine()

        assert result is mock_engine