# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import os
import re
import subprocess
import time
import json
from threading import Timer
from collections import defaultdict, deque
import asyncio
import uuid
import atexit
import signal
import threading

# Redis and Celery imports
import redis
from celery import Celery

# from dotenv import load_dotenv
# load_dotenv()

# Redis クライアント設定
redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

# Celery クライアント設定
celery_app = Celery('discord_bot')
celery_app.config_from_object({
    'broker_url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
})

# レガシーサポート用（段階的移行）
queue_dict = defaultdict(deque)
connecting_channels = set()
active_processes = set()
cleanup_lock = threading.Lock()

# 音声キューモニタリング状態
queue_monitors = {}

dictID = int(os.environ['DICT_CH_ID'])
dictMsg = None

userNicknameDict:dict[int,str] = dict ()

def enqueue(voice_client: discord.VoiceClient, guild: discord.guild, source, filename: str):
    # ボイスクライアントが存在しない場合は、キューに追加せずに終了
    if not voice_client:
        return
    
    queue = queue_dict[guild.id]
    queue.append([source, filename])
    
    if not voice_client.is_playing():
        play(voice_client, queue)


def play(voice_client: discord.VoiceClient, queue: deque):
    if not queue or voice_client.is_playing():
        return
    source = queue.popleft()
    
    def after_play(error):
        if error:
            print(f"Player error: {error}")
        # Clean up the audio file after playing
        try:
            if os.path.exists(source[1]):
                os.remove(source[1])
        except Exception as e:
            print(f"Failed to remove audio file {source[1]}: {e}")
        # Continue playing next item in queue
        play(voice_client, queue)
    
    voice_client.play(source[0], after=after_play)


def current_milli_time() -> int:
    return round(time.time() * 1000)


async def addDict(arg1: str, arg2: str, guild_id: int = None):
    """辞書にエントリを追加（Redis + レガシー対応）"""
    global dictMsg
    
    # Redis に保存
    if guild_id:
        dict_key = f"dict:{guild_id}"
        dict_data = redis_client.hget(dict_key, "entries")
        entries = json.loads(dict_data) if dict_data else {}
        entries[arg1] = arg2
        redis_client.hset(dict_key, "entries", json.dumps(entries))
    
    # レガシー対応
    msg = dictMsg.content + '\n' + arg1 + ',' + arg2
    dictMsg = await dictMsg.edit(content=msg)
    print(msg)


def showDict(guild_id: int = None) -> str:
    """辞書一覧表示（Redis + レガシー対応）"""
    global dictMsg
    
    # Redis から取得を試行
    if guild_id:
        dict_key = f"dict:{guild_id}"
        dict_data = redis_client.hget(dict_key, "entries")
        if dict_data:
            entries = json.loads(dict_data)
            output = "現在登録されている辞書一覧\n"
            for index, (key, value) in enumerate(entries.items(), 1):
                output += f"{index}: {key} -> {value}\n"
            return output
    
    # レガシー対応
    msg = dictMsg.content
    lines = msg.splitlines()
    print(lines)
    output = "現在登録されている辞書一覧\n"
    for index, line in enumerate(lines):
        if index:
            pattern = line.strip().split(',')
            if len(pattern) >= 2:
                output += "{0}: {1} -> {2}\n".format(index, pattern[0], pattern[1])
    return output


async def removeDict(num: int, guild_id: int = None) -> bool:
    """辞書エントリ削除（Redis + レガシー対応）"""
    if num <= 0:
        return True
    
    global dictMsg
    
    # Redis から削除を試行
    if guild_id:
        dict_key = f"dict:{guild_id}"
        dict_data = redis_client.hget(dict_key, "entries")
        if dict_data:
            entries = json.loads(dict_data)
            entries_list = list(entries.items())
            if 1 <= num <= len(entries_list):
                key_to_remove = entries_list[num - 1][0]
                del entries[key_to_remove]
                redis_client.hset(dict_key, "entries", json.dumps(entries))
                return True
    
    # レガシー対応
    msg = dictMsg.content
    lines = msg.splitlines()
    output = []
    for index, line in enumerate(lines):
        if index != num:
            output.append(line)
    dictMsg = await dictMsg.edit(content='\n'.join(output))
    return True


def replaceDict(text: str, guild_id: int = None) -> str:
    """辞書置換処理（Redis + レガシー対応）"""
    global dictMsg
    
    # Redis から置換を試行
    if guild_id:
        dict_key = f"dict:{guild_id}"
        dict_data = redis_client.hget(dict_key, "entries")
        if dict_data:
            entries = json.loads(dict_data)
            for pattern, replacement in entries.items():
                if pattern in text:
                    text = text.replace(pattern, replacement)
            return text
    
    # レガシー対応
    msg = dictMsg.content
    lines = msg.splitlines()
    for line in lines:
        pattern = line.strip().split(',')
        if len(pattern) >= 2 and pattern[0] in text:
            text = text.replace(pattern[0], pattern[1])
    return text


def replaceStamp(text: str) -> str:
    text = re.sub('<:([^:]*):.*>', '\\1', text)
    return text


async def replaceUserName(text: str) -> str:
    for word in text.split():
        if not mention.match(word):
            continue
        print(word)
        userId = re.sub('<@([^>]*)>', '\\1', word)
        print(userId)
        userName = str(await bot.fetch_user(userId))
        userName = re.sub('#.*', '', userName)
        text = text.replace(word, '@' + userName)
    return text


async def jtalk(t) -> str:
    open_jtalk = ['open_jtalk']
    mech = ['-x', '/var/lib/mecab/dic/open-jtalk/naist-jdic']
    htsvoice = ['-m', '/usr/share/hts-voice/mei/mei_normal.htsvoice']
    pitch = ['-fm', '-5']
    speed = ['-r', '1.0']
    
    # Generate unique filename to avoid conflicts
    filename = f'output_{uuid.uuid4().hex[:8]}.wav'
    outwav = ['-ow', filename]
    cmd = open_jtalk + mech + htsvoice + pitch + speed + outwav
    
    try:
        c = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with cleanup_lock:
            active_processes.add(c)
        
        stdout, stderr = c.communicate(input=t.encode(), timeout=30)
        
        if c.returncode != 0:
            raise Exception(f"OpenJTalk failed: {stderr.decode()}")
            
        return filename
    except subprocess.TimeoutExpired:
        c.kill()
        raise Exception("OpenJTalk timeout")
    except Exception as e:
        if os.path.exists(filename):
            os.remove(filename)
        raise e
    finally:
        with cleanup_lock:
            active_processes.discard(c)


def get_voice_client(channel_id: int) -> discord.VoiceClient | None:
    for client in bot.voice_clients:
        if client.channel and client.channel.id == channel_id:
            return client
    else:
        return None


async def check_voice_client_health(voice_client: discord.VoiceClient) -> bool:
    """Check if voice client is healthy and can play audio"""
    try:
        if not voice_client or not voice_client.is_connected():
            return False
        # Test if the voice client is responsive
        return True
    except Exception as e:
        print(f"Voice client health check failed: {e}")
        return False


async def ensure_voice_connection(guild: discord.Guild, channel_id: int) -> discord.VoiceClient | None:
    """Ensure we have a healthy voice connection"""
    voice_client = get_voice_client(channel_id)
    
    if voice_client and await check_voice_client_health(voice_client):
        return voice_client
    
    # Reconnect if connection is unhealthy
    if voice_client:
        try:
            await voice_client.disconnect()
        except:
            pass
    
    try:
        channel = bot.get_channel(channel_id)
        if channel:
            return await channel.connect()
    except Exception as e:
        print(f"Failed to reconnect to voice channel: {e}")
        return None


async def text_check(text: str, user_name: str, guild_id: int = None) -> str:
    """テキストの前処理（TTS生成前の準備）"""
    print(text)
    if len(text) > 150:
        raise Exception("文字数が長すぎるよ")
    if stamp.search(text):
        text = replaceStamp(text)
    if mention.search(text):
        text = await replaceUserName(text)
    
    text = re.sub('http.*', '', text)
    text = replaceDict(text, guild_id)
    text = user_name + text
    if len(text) > 150:
        raise Exception("文字数が長すぎるよ")
    
    return text

async def submit_tts_task(text: str, user_name: str, guild_id: int, channel_id: int) -> str:
    """TTS生成タスクをワーカーに送信"""
    task_id = str(uuid.uuid4())
    
    try:
        # テキストの前処理
        processed_text = await text_check(text, user_name, guild_id)
        
        # Celeryタスクとして非同期実行
        celery_app.send_task(
            'tts_worker.generate_tts_task',
            args=[task_id, processed_text, user_name, guild_id, channel_id],
            queue='tts_queue'
        )
        
        print(f"TTS task submitted: {task_id} for guild {guild_id}")
        return task_id
        
    except Exception as e:
        print(f"Failed to submit TTS task: {e}")
        raise e

async def start_audio_queue_monitor(guild_id: int, channel_id: int):
    """音声キューの監視を開始"""
    if guild_id in queue_monitors:
        return  # 既に監視中
    
    queue_monitors[guild_id] = True
    
    try:
        while queue_monitors.get(guild_id, False):
            try:
                # Redisから次の音声タスクを取得（ブロッキング）
                result = redis_client.brpop(f"audio:queue:{guild_id}", timeout=1)
                
                if result:
                    task_id = result[1].decode()
                    await process_audio_task(task_id, guild_id, channel_id)
                    
            except redis.exceptions.ConnectionError:
                print(f"Redis connection error for guild {guild_id}")
                await asyncio.sleep(5)
            except Exception as e:
                print(f"Audio queue monitor error for guild {guild_id}: {e}")
                await asyncio.sleep(1)
                
    finally:
        queue_monitors.pop(guild_id, None)

async def process_audio_task(task_id: str, guild_id: int, channel_id: int):
    """生成された音声を再生キューに追加"""
    try:
        # 音声情報をRedisから取得
        audio_data = redis_client.get(f"audio:{task_id}")
        if not audio_data:
            print(f"Audio data not found for task {task_id}")
            return
        
        audio_info = json.loads(audio_data)
        filename = audio_info['filename']
        
        # ファイルの存在確認
        if not os.path.exists(filename):
            print(f"Audio file not found: {filename}")
            return
        
        # ボイスクライアントを取得
        voice_client = get_voice_client(channel_id)
        if not voice_client:
            print(f"Voice client not found for channel {channel_id}")
            # ファイルをクリーンアップ
            if os.path.exists(filename):
                os.remove(filename)
            return
        
        # 音声を再生キューに追加
        enqueue(voice_client, await bot.fetch_guild(guild_id), 
               discord.FFmpegPCMAudio(filename), filename)
        
        print(f"Audio queued for playback: {task_id}")
        
    except Exception as e:
        print(f"Failed to process audio task {task_id}: {e}")


client_id = os.environ['DISCORD_CLIENT_ID']
application_id = os.environ['DISCORD_APP_ID']
# クライアント、コマンドツリーを作成
bot = commands.Bot(
    command_prefix="/",
    intents=discord.Intents.all(),
    application_id=application_id
)
tree = bot.tree
# client = discord.Client(intents=discord.Intents.all())
# tree = discord.app_commands.CommandTree(client)

voice = None
volume = None
currentChannel = None

url = re.compile('^http')
mention = re.compile('<@[^>]*>')
stamp = re.compile('<:([^:]*):.*>')


@bot.event
async def on_ready():
    # 起動時の処理

    global dictMsg
    channel = bot.get_channel(dictID)
    print(channel)
    async for message in channel.history(limit=1):
        if message.author == bot.user:
            dictMsg = message
        else:
            dictMsg = await channel.send('文字列,文字列')
    await tree.sync()
    print('Bot is wake up. hi bro.')

"""おてほん
@tree.command(name="コマンド名",description="説明")
async def f(interaction:discord.Interaction):
    # 中身 https://discordpy.readthedocs.io/ja/latest/interactions/api.html#interaction
    # を見るとinteractionから取得できる情報が分かるよ
    await interaction.response.send_message("返信はコマンド入力に対して一回きりだよ")

#コピペ用
@tree.command(name="",description="")
async def f(interaction:discord.Interaction):
    await interaction.response.send_message()
"""


@tree.command(name="join", description="ボイスチャンネルに参加するよ")
async def join(interaction: discord.Interaction):
    await interaction.response.defer()
    print(f"join:{interaction.channel}")
    connecting_channels.add(interaction.channel_id)
    await interaction.followup.send('ボイスチャンネルに参加します')
    try:
        global currentChannel
        currentChannel = interaction.channel_id
        await interaction.channel.connect()
    except Exception as e:
        connecting_channels.remove(interaction.channel_id)
        await interaction.followup.send(f"参加中に異常が発生しました\n```{e}```")


@tree.command(name="dc", description="ボイスチャンネルから退出するよ")
async def dc(interaction: discord.Interaction):
    await interaction.response.defer()
    client: discord.VoiceClient | None = get_voice_client(
        interaction.channel_id)

    if client:
        global currentChannel
        currentChannel = None
        guild_id = interaction.guild.id
        
        # 音声キューモニタリングを停止
        queue_monitors.pop(guild_id, None)
        
        # Redis キューをクリア
        redis_client.delete(f"audio:queue:{guild_id}")
        
        # レガシーキューもクリア
        if guild_id in queue_dict:
            queue_dict[guild_id].clear()
            
        await client.disconnect()
        await interaction.followup.send('ボイスチャンネルからログアウトしました')
    else:
        await interaction.followup.send('ボイスチャンネルに参加していません')


@tree.command(name="status", description="現在のステータスを確認するよ")
async def f(interaction: discord.Interaction):

    if get_voice_client(interaction.channel_id):
        status = "ボイスチャンネルに接続中だよ"
    else:
        status = "ボイスチャンネルに接続してないよ"
    await interaction.response.send_message(status)


@tree.command(name="volume", description="音量を調整するよ")
async def vol(interaction: discord.Interaction, control: str):
    global volume

    if control == "up":
        volume += 0.1
        await interaction.response.send_message(f"音量を上げました\n現在の音量:{volume}")
    elif control == "down":
        volume -= 0.1
        await interaction.response.send_message(f"音量を下げました\n現在の音量:{volume}")
    else:
        await interaction.response.send_message(f"up もしくは down を入力してください\n現在の音量:{volume}")


@tree.command(name="bye", description="クライアント終了、仕様上動くかわかんない")
async def bye(interaction: discord.Interaction):
    await interaction.response.send_message("クライアントを終了します")
    await bot.close()


@tree.command(name="kill", description="ボットプロセスを強制終了します")
async def kill(interaction: discord.Interaction):
    await interaction.response.send_message("ボットプロセスを強制終了します。")
    cleanup_processes()
    os._exit(1)


@tree.command(name="get", description="辞書の内容を取得するよ")
async def get(interaction: discord.Interaction):
    await interaction.response.send_message(showDict(interaction.guild_id))


@tree.command(name="add", description="辞書に新しい単語を登録するよ")
@discord.app_commands.describe(arg1="置換前の単語を入れてね", arg2="置換後の単語を入れてね")
async def add(interaction: discord.Interaction, arg1: str, arg2: str):
    if len(arg1) > 10 or len(arg2) > 10:
        return await interaction.response.send_message("荒らしは許されませんよ♡\n置換する単語は10文字以内にしてね")
    await addDict(arg1, arg2, interaction.guild_id)
    await interaction.response.send_message(f"{arg1}を{arg2}と読むように辞書に登録しました！")


@tree.command(name="remove", description="辞書の単語を削除するよ")
@discord.app_commands.describe(num="削除する単語の番号を入れてね")
async def remove(interaction: discord.Interaction, num: int):
    if await removeDict(num, interaction.guild_id):
        await interaction.response.send_message("削除しました")
    else:
        await interaction.response.send_message("エラーが発生しました")
        
@tree.command(name="rename", description="あなたの呼び方を変えるよ")
@discord.app_commands.describe(name="あなたの呼び方を入れてね")
async def rename(interaction: discord.Interaction, name: str=None):
    if not name:
        nickname = get_user_nickname(interaction.user.id, interaction.guild_id)
        if nickname:
            return await interaction.response.send_message(f"あなたの呼び方は{nickname}だよ")
        else:
            return await interaction.response.send_message(f"あなたの呼び方はまだ設定されてないよ")
    if len(name) > 10:
        return await interaction.response.send_message("荒らしは許されませんよ♡\n呼び方は10文字以内にしてね")
    set_user_nickname(interaction.user.id, name, interaction.guild_id)
    await interaction.response.send_message(f"あなたの呼び方を{name}に変えたよ")

def get_user_nickname(user_id: int, guild_id: int = None) -> str | None:
    """ユーザーニックネームを取得（Redis + レガシー対応）"""
    # Redis から取得を試行
    if guild_id:
        nickname = redis_client.hget(f"user:nickname:{guild_id}", str(user_id))
        if nickname:
            return nickname.decode()
    
    # レガシー対応
    return userNicknameDict.get(user_id)

def set_user_nickname(user_id: int, nickname: str, guild_id: int = None):
    """ユーザーニックネームを設定（Redis + レガシー対応）"""
    # Redis に保存
    if guild_id:
        redis_client.hset(f"user:nickname:{guild_id}", str(user_id), nickname)
    
    # レガシー対応
    userNicknameDict[user_id] = nickname

@bot.event
async def on_message(message: discord.Message):
    # テキストチャンネルにメッセージが送信されたときの処理
    global volume

    # botの排除
    if message.author.bot:
        return await bot.process_commands(message)
    volume = 0.5

    voice = get_voice_client(message.channel.id)

    if not voice:
        return await bot.process_commands(message)

    if voice is True and volume is None:
        source = discord.PCMVolumeTransformer(voice.source)
        volume = source.volume

    text = message.content
    guild_id = message.guild.id
    channel_id = message.channel.id

    # ユーザーニックネーム取得
    user_name = get_user_nickname(message.author.id, guild_id)
    if not user_name:
        user_name = message.author.display_name
    
    try:
        # TTS生成タスクを非同期で送信
        task_id = await submit_tts_task(text, user_name, guild_id, channel_id)
        
        # 音声キューモニタリングを開始（既に開始済みの場合は何もしない）
        asyncio.create_task(start_audio_queue_monitor(guild_id, channel_id))
        
    except Exception as e:
        print(f"TTS task submission error: {e}")
        return await message.channel.send(f"読み上げエラー: {e}")

    # Ensure voice connection is healthy
    voice_client = await ensure_voice_connection(message.guild, message.channel.id)
    if not voice_client:
        print("Failed to establish voice connection")
        return await bot.process_commands(message)
    
    # コマンド側へメッセージ内容を渡す
    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member: discord.Member, before:discord.VoiceState, after:discord.VoiceState):
    # Chatに接続中でないなら処理しない
    global currentChannel
    if currentChannel is None:
        return
    
    guild_id = member.guild.id
    username = get_user_nickname(member.id, guild_id)
    if not username:
        username = member.display_name
        
    if not before.channel and after.channel:
        try:
            # 挨拶メッセージをTTSタスクとして送信
            greeting_text = username + "さんこんにちは！"
            await submit_tts_task(greeting_text, "", guild_id, currentChannel)
        except Exception as e:
            print(f"Failed to submit greeting TTS: {e}")
            
    if before.channel and not after.channel:
        try:
            # 退出メッセージをTTSタスクとして送信
            farewell_text = username + "さんが退出しました"
            await submit_tts_task(farewell_text, "", guild_id, currentChannel)
        except Exception as e:
            print(f"Failed to submit farewell TTS: {e}")
            
    # ボットだけが残った場合の自動退出処理
    if before.channel:
        allbot = True    
        selfcheck = False
        for mem in before.channel.members:
            if mem.id == bot.user.id:
                selfcheck = True
            if not mem.bot:
                allbot = False
                
        if allbot and selfcheck:
            client = member.guild.voice_client
            if client:
                # 音声キューモニタリングを停止
                queue_monitors.pop(guild_id, None)
                
                # Redis キューをクリア
                redis_client.delete(f"audio:queue:{guild_id}")
                
                # レガシーキューもクリア
                if guild_id in queue_dict:
                    queue_dict[guild_id].clear()
                    
                await client.disconnect()
                await before.channel.send('ボイスチャンネルからログアウトしました')

def cleanup_processes():
    """Clean up any remaining OpenJTalk processes on exit"""
    with cleanup_lock:
        for process in list(active_processes):
            try:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=5)
            except:
                try:
                    process.kill()
                except:
                    pass
        active_processes.clear()


# Register cleanup handlers
atexit.register(cleanup_processes)
signal.signal(signal.SIGTERM, lambda signum, frame: cleanup_processes())
signal.signal(signal.SIGINT, lambda signum, frame: cleanup_processes())


async def main():
    # start the client
    try:
        async with bot:
            await bot.start(client_id)
    except Exception as e:
        print(f"Bot startup failed: {e}")
    finally:
        cleanup_processes()


if __name__ == "__main__":
    asyncio.run(main())
