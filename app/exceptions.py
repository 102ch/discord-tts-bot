# -*- coding: utf-8 -*-
"""
Custom exceptions for Discord TTS Bot
"""


class TTSBotError(Exception):
    """Base exception class for TTS Bot"""
    pass


class TextTooLongError(TTSBotError):
    """Raised when text is too long for TTS"""
    def __init__(self, length: int, max_length: int):
        self.length = length
        self.max_length = max_length
        super().__init__(f"テキストが長すぎます ({length}/{max_length}文字)")


class FileTooLargeError(TTSBotError):
    """Raised when generated audio file is too large"""
    def __init__(self, size: int, max_size: int):
        self.size = size
        self.max_size = max_size
        super().__init__(f"音声ファイルが大きすぎます ({size}/{max_size}バイト)")


class VoiceChannelError(TTSBotError):
    """Raised when voice channel operations fail"""
    pass


class DictionaryError(TTSBotError):
    """Raised when dictionary operations fail"""
    pass


class TTSProcessError(TTSBotError):
    """Raised when TTS processing fails"""
    pass