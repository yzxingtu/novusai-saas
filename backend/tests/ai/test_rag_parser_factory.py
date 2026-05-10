"""Parser factory coverage for multimodal KB / 多模态知识库解析器工厂测试。

Test type: structural / behavioral
Scope: Existing AI tests in this module; no real-dialogue smoke acceptance is claimed.
"""

from app.ai.rag.parser import AudioParser, VideoParser, get_parser


def test_get_parser_returns_audio_parser_for_audio_types():
    parser = get_parser("audio")
    assert isinstance(parser, AudioParser)


def test_get_parser_returns_video_parser_for_video_types():
    parser = get_parser("video")
    assert isinstance(parser, VideoParser)
