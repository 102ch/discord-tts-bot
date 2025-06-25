# -*- coding: utf-8 -*-
"""
Configuration settings for Discord TTS Bot
"""
import os
from typing import Optional


def get_env_var(key: str, default: Optional[str] = None) -> str:
    """安全に環境変数を取得する"""
    value = os.environ.get(key, default)
    if value is None:
        raise ValueError(f"環境変数 {key} が設定されていません")
    return value


# Discord設定
DISCORD_CLIENT_ID = get_env_var('DISCORD_CLIENT_ID')
DISCORD_APP_ID = get_env_var('DISCORD_APP_ID')
DICT_CH_ID = int(get_env_var('DICT_CH_ID'))

# TTS設定
MAX_TEXT_LENGTH = 150
MAX_FILE_SIZE = 10000000
MAX_DICT_WORD_LENGTH = 10
TTS_VOICE_PATH = "/usr/share/hts-voice/mei/mei_normal.htsvoice"
TTS_SPEED = "1.0"
TTS_PITCH = "-5"

# オーディオ設定
DEFAULT_VOLUME = 0.5
VOLUME_STEP = 0.1

# ファイル設定
OUTPUT_AUDIO_FILE = "output.wav"
TEMP_FILE_CLEANUP_DELAY = 3  # seconds

# 正規表現パターン
URL_PATTERN = r'^http'
MENTION_PATTERN = r'<@[^>]*>'
STAMP_PATTERN = r'<:([^:]*):.*>'