# -*- coding: utf-8 -*-
"""
Discord TTS Bot - Improved Version
OpenJTalkを用いてDiscordのチャットに投稿されたメッセージをVoice Chatで読み上げるBot
"""
import discord
from discord.ext import commands
import os
import re
import subprocess
import time
import asyncio
import logging
from threading import Timer
from collections import defaultdict, deque
from typing import Dict, Deque, Set, Optional, Tuple

# ローカルインポート
from config import *
from exceptions import *

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TTSBot:
    """Discord TTS Bot のメインクラス"""
    
    def __init__(self):
        """Initialize the TTS Bot"""
        self.queue_dict: Dict[int, Deque] = defaultdict(deque)
        self.connecting_channels: Set[int] = set()
        self.user_nickname_dict: Dict[int, str] = {}
        self.dict_msg: Optional[discord.Message] = None
        self.current_channel: Optional[int] = None
        self.volume: float = DEFAULT_VOLUME
        
        # 正規表現パターンをコンパイル
        self.url_pattern = re.compile(URL_PATTERN)
        self.mention_pattern = re.compile(MENTION_PATTERN)
        self.stamp_pattern = re.compile(STAMP_PATTERN)
        
        # Discord Bot設定
        self.bot = commands.Bot(
            command_prefix="/",
            intents=discord.Intents.all(),
            application_id=DISCORD_APP_ID
        )
        self.tree = self.bot.tree
        
        # イベントハンドラーの登録
        self._register_events()
        self._register_commands()
    
    def _register_events(self):
        """イベントハンドラーの登録"""
        
        @self.bot.event
        async def on_ready():
            await self._on_ready()
            
        @self.bot.event
        async def on_message(message: discord.Message):
            await self._on_message(message)
            
        @self.bot.event
        async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
            await self._on_voice_state_update(member, before, after)
    
    def _register_commands(self):
        """スラッシュコマンドの登録"""
        
        @self.tree.command(name="join", description="ボイスチャンネルに参加するよ")
        async def join(interaction: discord.Interaction):
            await self._cmd_join(interaction)
            
        @self.tree.command(name="dc", description="ボイスチャンネルから退出するよ")
        async def dc(interaction: discord.Interaction):
            await self._cmd_dc(interaction)
            
        @self.tree.command(name="status", description="現在のステータスを確認するよ")
        async def status(interaction: discord.Interaction):
            await self._cmd_status(interaction)
            
        @self.tree.command(name="volume", description="音量を調整するよ")
        @discord.app_commands.describe(control="up または down")
        async def volume(interaction: discord.Interaction, control: str):
            await self._cmd_volume(interaction, control)
            
        @self.tree.command(name="bye", description="クライアント終了")
        async def bye(interaction: discord.Interaction):
            await self._cmd_bye(interaction)
            
        @self.tree.command(name="get", description="辞書の内容を取得するよ")
        async def get(interaction: discord.Interaction):
            await self._cmd_get(interaction)
            
        @self.tree.command(name="add", description="辞書に新しい単語を登録するよ")
        @discord.app_commands.describe(arg1="置換前の単語を入れてね", arg2="置換後の単語を入れてね")
        async def add(interaction: discord.Interaction, arg1: str, arg2: str):
            await self._cmd_add(interaction, arg1, arg2)
            
        @self.tree.command(name="remove", description="辞書の単語を削除するよ")
        @discord.app_commands.describe(num="削除する単語の番号を入れてね")
        async def remove(interaction: discord.Interaction, num: int):
            await self._cmd_remove(interaction, num)
            
        @self.tree.command(name="rename", description="あなたの呼び方を変えるよ")
        @discord.app_commands.describe(name="あなたの呼び方を入れてね")
        async def rename(interaction: discord.Interaction, name: Optional[str] = None):
            await self._cmd_rename(interaction, name)
    
    async def _on_ready(self):
        """Bot起動時の処理"""
        try:
            # 辞書チャンネルの初期化
            channel = self.bot.get_channel(DICT_CH_ID)
            if not channel:
                logger.error(f"辞書チャンネル {DICT_CH_ID} が見つかりません")
                return
                
            async for message in channel.history(limit=1):
                if message.author == self.bot.user:
                    self.dict_msg = message
                    break
            else:
                self.dict_msg = await channel.send('文字列,文字列')
            
            await self.tree.sync()
            logger.info('Bot is ready!')
            
        except Exception as e:
            logger.error(f"Bot初期化エラー: {e}")
    
    async def _on_message(self, message: discord.Message):
        """メッセージ受信時の処理"""
        try:
            # Botメッセージの除外
            if message.author.bot:
                return await self.bot.process_commands(message)
            
            # ボイスクライアントの確認
            voice = self._get_voice_client(message.channel.id)
            if not voice:
                return await self.bot.process_commands(message)
            
            # ユーザー名の取得
            user_name = self.user_nickname_dict.get(
                message.author.id, 
                message.author.display_name
            ) or message.author.display_name
            
            # テキスト処理とTTS生成
            text, filename = await self._process_text(message.content, user_name)
            
            # キューに追加
            if message.guild.voice_client:
                self._enqueue(
                    message.guild.voice_client, 
                    message.guild,
                    discord.FFmpegPCMAudio(filename), 
                    filename
                )
            
            await self.bot.process_commands(message)
            
        except TTSBotError as e:
            await message.channel.send(str(e))
        except Exception as e:
            logger.error(f"メッセージ処理エラー: {e}")
            await message.channel.send("メッセージの処理中にエラーが発生しました")
    
    async def _on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """ボイスチャンネル状態変更時の処理"""
        try:
            if self.current_channel is None:
                return
                
            username = self.user_nickname_dict.get(member.id, member.display_name)
            
            # 入室時
            if not before.channel and after.channel:
                filename = await self._generate_tts(f"{username}さんこんにちは！")
                self._enqueue(
                    member.guild.voice_client, 
                    member.guild,
                    discord.FFmpegPCMAudio(filename), 
                    filename
                )
            
            # 退室時
            elif before.channel and not after.channel:
                filename = await self._generate_tts(f"{username}さんが退出しました")
                self._enqueue(
                    member.guild.voice_client, 
                    member.guild,
                    discord.FFmpegPCMAudio(filename), 
                    filename
                )
                
                # 自動退出チェック
                if before.channel:
                    all_bots = True
                    bot_in_channel = False
                    
                    for mem in before.channel.members:
                        if mem.id == self.bot.user.id:
                            bot_in_channel = True
                        if not mem.bot:
                            all_bots = False
                    
                    if all_bots and bot_in_channel:
                        client = member.guild.voice_client
                        if client:
                            await client.disconnect()
                            await before.channel.send('ボイスチャンネルからログアウトしました')
        
        except Exception as e:
            logger.error(f"ボイス状態更新エラー: {e}")
    
    def _enqueue(self, voice_client: discord.VoiceClient, guild: discord.Guild, source, filename: str):
        """音声をキューに追加"""
        queue = self.queue_dict[guild.id]
        queue.append([source, filename])
        
        if voice_client and not voice_client.is_playing():
            self._play(voice_client, queue)
    
    def _play(self, voice_client: discord.VoiceClient, queue: Deque):
        """音声を再生"""
        if not queue or voice_client.is_playing():
            return
            
        source_info = queue.popleft()
        voice_client.play(source_info[0], after=lambda e: self._play(voice_client, queue))
    
    def _get_voice_client(self, channel_id: int) -> Optional[discord.VoiceClient]:
        """指定チャンネルのボイスクライアントを取得"""
        for client in self.bot.voice_clients:
            if client.channel.id == channel_id:
                return client
        return None
    
    async def _process_text(self, text: str, user_name: str) -> Tuple[str, str]:
        """テキストを処理してTTS用に変換"""
        # 文字数チェック
        if len(text) > MAX_TEXT_LENGTH:
            raise TextTooLongError(len(text), MAX_TEXT_LENGTH)
        
        # スタンプ置換
        if self.stamp_pattern.search(text):
            text = self._replace_stamp(text)
        
        # メンション置換
        if self.mention_pattern.search(text):
            text = await self._replace_user_name(text)
        
        # URL除去
        text = re.sub(self.url_pattern, '', text)
        
        # 辞書置換
        text = self._replace_dict(text)
        
        # ユーザー名追加
        text = user_name + text
        
        # 最終文字数チェック
        if len(text) > MAX_TEXT_LENGTH:
            raise TextTooLongError(len(text), MAX_TEXT_LENGTH)
        
        # TTS生成
        filename = await self._generate_tts(text)
        
        # ファイルサイズチェック
        if os.path.getsize(filename) > MAX_FILE_SIZE:
            os.remove(filename)
            raise FileTooLargeError(os.path.getsize(filename), MAX_FILE_SIZE)
        
        return text, filename
    
    async def _generate_tts(self, text: str) -> str:
        """Open JTalkを使ってTTSファイルを生成"""
        try:
            filename = f"temp/output_{int(time.time() * 1000)}.wav"
            os.makedirs("temp", exist_ok=True)
            
            cmd = [
                'open_jtalk',
                '-x', '/var/lib/mecab/dic/open-jtalk/naist-jdic',
                '-m', TTS_VOICE_PATH,
                '-fm', TTS_PITCH,
                '-r', TTS_SPEED,
                '-ow', filename
            ]
            
            process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = process.communicate(input=text.encode('utf-8'))
            
            if process.returncode != 0:
                raise TTSProcessError(f"TTS生成エラー: {stderr.decode('utf-8', errors='ignore')}")
            
            return filename
            
        except Exception as e:
            logger.error(f"TTS生成エラー: {e}")
            raise TTSProcessError(f"音声生成に失敗しました: {e}")
    
    def _replace_stamp(self, text: str) -> str:
        """スタンプを置換"""
        return re.sub(self.stamp_pattern, r'\1', text)
    
    async def _replace_user_name(self, text: str) -> str:
        """メンションをユーザー名に置換"""
        for word in text.split():
            if not self.mention_pattern.match(word):
                continue
                
            try:
                user_id = re.sub(r'<@([^>]*)>', r'\1', word)
                user = await self.bot.fetch_user(int(user_id))
                user_name = re.sub(r'#.*', '', str(user))
                text = text.replace(word, f'@{user_name}')
            except Exception as e:
                logger.warning(f"ユーザー名置換エラー: {e}")
                
        return text
    
    def _replace_dict(self, text: str) -> str:
        """辞書を使ってテキストを置換"""
        if not self.dict_msg:
            return text
            
        try:
            lines = self.dict_msg.content.splitlines()
            for line in lines[1:]:  # 最初の行はヘッダーなのでスキップ
                if ',' in line:
                    pattern = line.strip().split(',', 1)
                    if len(pattern) >= 2 and pattern[0] in text:
                        text = text.replace(pattern[0], pattern[1])
        except Exception as e:
            logger.warning(f"辞書置換エラー: {e}")
            
        return text
    
    # コマンドハンドラーメソッド群
    async def _cmd_join(self, interaction: discord.Interaction):
        """join コマンドのハンドラー"""
        await interaction.response.defer()
        
        try:
            if interaction.user.voice is None or interaction.user.voice.channel is None:
                await interaction.followup.send("ボイスチャンネルに接続してからコマンドを実行してください")
                return
            
            self.connecting_channels.add(interaction.channel_id)
            self.current_channel = interaction.channel_id
            
            await interaction.user.voice.channel.connect()
            await interaction.followup.send('ボイスチャンネルに参加しました')
            
        except Exception as e:
            self.connecting_channels.discard(interaction.channel_id)
            logger.error(f"Join エラー: {e}")
            await interaction.followup.send(f"参加中に異常が発生しました: {e}")
    
    async def _cmd_dc(self, interaction: discord.Interaction):
        """dc コマンドのハンドラー"""
        await interaction.response.defer()
        
        client = self._get_voice_client(interaction.channel_id)
        if client:
            self.current_channel = None
            await client.disconnect()
            await interaction.followup.send('ボイスチャンネルからログアウトしました')
        else:
            await interaction.followup.send('ボイスチャンネルに参加していません')
    
    async def _cmd_status(self, interaction: discord.Interaction):
        """status コマンドのハンドラー"""
        if self._get_voice_client(interaction.channel_id):
            status = "ボイスチャンネルに接続中だよ"
        else:
            status = "ボイスチャンネルに接続してないよ"
        await interaction.response.send_message(status)
    
    async def _cmd_volume(self, interaction: discord.Interaction, control: str):
        """volume コマンドのハンドラー"""
        if control == "up":
            self.volume = min(1.0, self.volume + VOLUME_STEP)
            await interaction.response.send_message(f"音量を上げました\n現在の音量: {self.volume:.1f}")
        elif control == "down":
            self.volume = max(0.0, self.volume - VOLUME_STEP)
            await interaction.response.send_message(f"音量を下げました\n現在の音量: {self.volume:.1f}")
        else:
            await interaction.response.send_message(f"up もしくは down を入力してください\n現在の音量: {self.volume:.1f}")
    
    async def _cmd_bye(self, interaction: discord.Interaction):
        """bye コマンドのハンドラー"""
        await interaction.response.send_message("クライアントを終了します")
        await self.bot.close()
    
    async def _cmd_get(self, interaction: discord.Interaction):
        """get コマンドのハンドラー"""
        dict_content = self._show_dict()
        await interaction.response.send_message(dict_content)
    
    async def _cmd_add(self, interaction: discord.Interaction, arg1: str, arg2: str):
        """add コマンドのハンドラー"""
        if len(arg1) > MAX_DICT_WORD_LENGTH or len(arg2) > MAX_DICT_WORD_LENGTH:
            await interaction.response.send_message(f"荒らしは許されませんよ♡\n置換する単語は{MAX_DICT_WORD_LENGTH}文字以内にしてね")
            return
        
        try:
            await self._add_dict(arg1, arg2)
            await interaction.response.send_message(f"{arg1}を{arg2}と読むように辞書に登録しました！")
        except Exception as e:
            logger.error(f"辞書追加エラー: {e}")
            await interaction.response.send_message("辞書の追加中にエラーが発生しました")
    
    async def _cmd_remove(self, interaction: discord.Interaction, num: int):
        """remove コマンドのハンドラー"""
        try:
            if await self._remove_dict(num):
                await interaction.response.send_message("削除しました")
            else:
                await interaction.response.send_message("削除に失敗しました")
        except Exception as e:
            logger.error(f"辞書削除エラー: {e}")
            await interaction.response.send_message("削除中にエラーが発生しました")
    
    async def _cmd_rename(self, interaction: discord.Interaction, name: Optional[str] = None):
        """rename コマンドのハンドラー"""
        if not name:
            if interaction.user.id in self.user_nickname_dict:
                nickname = self.user_nickname_dict[interaction.user.id]
                await interaction.response.send_message(f"あなたの呼び方は{nickname}だよ")
            else:
                await interaction.response.send_message("あなたの呼び方はまだ設定されてないよ")
            return
        
        if len(name) > MAX_DICT_WORD_LENGTH:
            await interaction.response.send_message(f"荒らしは許されませんよ♡\n呼び方は{MAX_DICT_WORD_LENGTH}文字以内にしてね")
            return
        
        self.user_nickname_dict[interaction.user.id] = name
        await interaction.response.send_message(f"あなたの呼び方を{name}に変えたよ")
    
    # 辞書操作メソッド群
    async def _add_dict(self, word: str, reading: str):
        """辞書に単語を追加"""
        if not self.dict_msg:
            raise DictionaryError("辞書メッセージが初期化されていません")
        
        new_content = self.dict_msg.content + '\n' + word + ',' + reading
        self.dict_msg = await self.dict_msg.edit(content=new_content)
    
    def _show_dict(self) -> str:
        """辞書の内容を表示用文字列で返す"""
        if not self.dict_msg:
            return "辞書が初期化されていません"
        
        lines = self.dict_msg.content.splitlines()
        output = "現在登録されている辞書一覧\n"
        
        for index, line in enumerate(lines):
            if index == 0:  # ヘッダー行をスキップ
                continue
            
            if ',' in line:
                pattern = line.strip().split(',', 1)
                if len(pattern) >= 2:
                    output += f"{index}: {pattern[0]} -> {pattern[1]}\n"
        
        return output if len(output) > len("現在登録されている辞書一覧\n") else "登録されている単語がありません"
    
    async def _remove_dict(self, num: int) -> bool:
        """辞書から指定番号の単語を削除"""
        if num <= 0 or not self.dict_msg:
            return False
        
        try:
            lines = self.dict_msg.content.splitlines()
            if num >= len(lines):
                return False
            
            new_lines = [line for i, line in enumerate(lines) if i != num]
            self.dict_msg = await self.dict_msg.edit(content='\n'.join(new_lines))
            return True
            
        except Exception as e:
            logger.error(f"辞書削除エラー: {e}")
            return False
    
    async def run(self):
        """Botを起動"""
        try:
            async with self.bot:
                await self.bot.start(DISCORD_CLIENT_ID)
        except Exception as e:
            logger.error(f"Bot起動エラー: {e}")
            raise


# メイン実行部分
async def main():
    """メイン関数"""
    tts_bot = TTSBot()
    await tts_bot.run()


if __name__ == "__main__":
    asyncio.run(main())