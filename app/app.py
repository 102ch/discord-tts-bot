# -*- coding: utf-8 -*-
import discord
from discord.ext import commands
import os
import re
import subprocess
import time
from threading import Timer
from collections import defaultdict, deque
import asyncio
import uuid
import atexit
import signal
import threading

# from dotenv import load_dotenv
# load_dotenv()

queue_dict = defaultdict(deque)
connecting_channels = set()
active_processes = set()
cleanup_lock = threading.Lock()

# Validate required environment variables
required_env_vars = ['DICT_CH_ID', 'DISCORD_CLIENT_ID', 'DISCORD_APP_ID']
missing_vars = [var for var in required_env_vars if var not in os.environ]
if missing_vars:
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

try:
    dictID = int(os.environ['DICT_CH_ID'])
except ValueError as e:
    raise ValueError(f"DICT_CH_ID must be a valid integer: {os.environ['DICT_CH_ID']}") from e

dictMsg = None

userNicknameDict:dict[int,str] = dict ()

def enqueue(voice_client: discord.VoiceClient, guild: discord.Guild, source, filename: str):
    # ボイスクライアントが存在しない、または接続されていない場合は、キューに追加せずに終了
    if not voice_client or not voice_client.is_connected():
        print("Voice client is not available or not connected. Skipping enqueue.")
        # Clean up the audio file
        try:
            if os.path.exists(filename):
                os.remove(filename)
        except Exception as e:
            print(f"Failed to remove audio file {filename}: {e}")
        return

    queue = queue_dict[guild.id]
    queue.append([source, filename])

    if not voice_client.is_playing():
        play(voice_client, queue)


def play(voice_client: discord.VoiceClient, queue: deque):
    if not queue or voice_client.is_playing():
        return

    # Check if voice client is still connected
    if not voice_client.is_connected():
        print("Voice client is not connected. Clearing queue.")
        # Clean up all pending audio files
        while queue:
            _, filename = queue.popleft()
            try:
                if os.path.exists(filename):
                    os.remove(filename)
            except Exception as e:
                print(f"Failed to remove audio file {filename}: {e}")
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

    try:
        voice_client.play(source[0], after=after_play)
    except Exception as e:
        print(f"Failed to play audio: {e}")
        # Clean up the file even if play fails
        try:
            if os.path.exists(source[1]):
                os.remove(source[1])
        except Exception as cleanup_error:
            print(f"Failed to remove audio file {source[1]}: {cleanup_error}")
        # Try to play next item in queue
        play(voice_client, queue)


def current_milli_time() -> int:
    return round(time.time() * 1000)


async def addDict(arg1: str, arg2: str):
    global dictMsg
    msg = dictMsg.content + '\n' + arg1 + ',' + arg2
    dictMsg = await dictMsg.edit(content=msg)
    print(msg)


def showDict() -> str:
    global dictMsg
    msg = dictMsg.content
    lines = msg.splitlines()
    print(lines)
    output = "現在登録されている辞書一覧\n"
    for index, line in enumerate(lines):
        if index:
            pattern = line.strip().split(',')
            output += "{0}: {1} -> {2}\n".format(index, pattern[0], pattern[1])
    return output


async def removeDict(num: int) -> bool:
    if num <= 0:
        return True
    global dictMsg
    msg = dictMsg.content
    lines = msg.splitlines()
    output = []
    for index, line in enumerate(lines):
        if index != num:
            output.append(line)
    dictMsg = await dictMsg.edit(content='\n'.join(output))
    return True


def replaceDict(text: str) -> str:
    global dictMsg
    msg = dictMsg.content
    lines = msg.splitlines()
    for line in lines:
        pattern = line.strip().split(',')
        if pattern[0] in text and len(pattern) >= 2:
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


async def text_check(text: str, user_name: str) -> tuple[str, str]:
    print(text)
    if len(text) > 150:
        raise Exception("文字数が長すぎるよ")
    if stamp.search(text):
        text = replaceStamp(text)
    if mention.search(text):
        text = await replaceUserName(text)

    # 改行を句点に置き換え
    text = text.replace('\n', '。')
    text = re.sub('http.*', '', text)
    text = replaceDict(text)
    text = user_name + text
    if len(text) > 150:
        raise Exception("文字数が長すぎるよ")
    
    try:
        filename = await jtalk(text)
        if os.path.getsize(filename) > 10000000:
            if os.path.exists(filename):
                os.remove(filename)
            raise Exception("再生時間が長すぎるよ")
        return text, filename
    except Exception as e:
        print(f"TTS generation failed: {e}")
        raise e


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
    print(f"Bot logged in as {bot.user} (ID: {bot.user.id})")

    global dictMsg
    try:
        channel = bot.get_channel(dictID)
        if channel is None:
            raise Exception(f"Dictionary channel with ID {dictID} not found. Please check DICT_CH_ID environment variable.")
        print(f"Found dictionary channel: {channel.name} (ID: {channel.id})")

        async for message in channel.history(limit=1):
            if message.author == bot.user:
                dictMsg = message
            else:
                dictMsg = await channel.send('文字列,文字列')

        await tree.sync()
        print('Bot is wake up. hi bro.')
    except Exception as e:
        print(f"FATAL ERROR during startup: {e}")
        import traceback
        traceback.print_exc()
        raise

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
        # キューをクリアして蓄積されたメッセージを削除
        if interaction.guild.id in queue_dict:
            queue_dict[interaction.guild.id].clear()
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
    cleanup_all()
    os._exit(1)


@tree.command(name="get", description="辞書の内容を取得するよ")
async def get(interaction: discord.Interaction):
    await interaction.response.send_message(showDict())


@tree.command(name="add", description="辞書に新しい単語を登録するよ")
@discord.app_commands.describe(arg1="置換前の単語を入れてね", arg2="置換後の単語を入れてね")
async def add(interaction: discord.Interaction, arg1: str, arg2: str):
    if len(arg1) > 10 or len(arg2) > 10:
        return await interaction.response.send_message("荒らしは許されませんよ♡\n置換する単語は10文字儼にしてね")
    await addDict(arg1, arg2)
    await interaction.response.send_message(f"{arg1}を{arg2}と読むように辞書に登録しました！")


@tree.command(name="remove", description="辞書の単語を削除するよ")
@discord.app_commands.describe(num="削除する単語の番号を入れてね")
async def remove(interaction: discord.Interaction, num: int):
    if await removeDict(num):
        await interaction.response.send_message("削除しました")
    else:
        await interaction.response.send_message("エラーが発生しました")
        
@tree.command(name="rename", description="あなたの呼び方を変えるよ")
@discord.app_commands.describe(name="あなたの呼び方を入れてね")
async def rename(interaction: discord.Interaction, name: str=None):
    if not name:
        if interaction.user.id in userNicknameDict:
            nickname=userNicknameDict[interaction.user.id]
            return await interaction.response.send_message(f"あなたの呼び方は{nickname}だよ")
        else:
            return await interaction.response.send_message(f"あなたの呼び方はまだ設定されてないよ")
    if len(name) > 10:
        return await interaction.response.send_message("荒らしは許されませんよ♡\n呼び方は10文字儼にしてね")
    userNicknameDict[interaction.user.id] = name
    await interaction.response.send_message(f"あなたの呼び方を{name}に変えたよ")

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

    if message.author.id in userNicknameDict:
        user_name=userNicknameDict[message.author.id]
    else:
        user_name=message.author.display_name
    
    try:
        text, filename = await text_check(text, user_name)
    except Exception as e:
        print(f"Text processing error: {e}")
        return await message.channel.send(f"読み上げエラー: {e}")

    # Ensure voice connection is healthy
    voice_client = await ensure_voice_connection(message.guild, message.channel.id)
    if not voice_client:
        print("Failed to establish voice connection")
        return await bot.process_commands(message)

    try:
        enqueue(voice_client, message.guild,
                discord.FFmpegPCMAudio(filename), filename)
    except Exception as e:
        print(f"Audio enqueue error: {e}")
        # Clean up file if enqueue fails
        if os.path.exists(filename):
            os.remove(filename)
        return await message.channel.send("音声の再生に失敗しました")
    
    # コマンド側へメッセージ内容を渡す
    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member: discord.Member, before:discord.VoiceState, after:discord.VoiceState):
    # Chatに接続中でないなら処理しない
    global currentChannel
    if currentChannel is None:
        return
    if member.id in userNicknameDict:
        username=userNicknameDict[member.id]
    else:
        username=member.display_name
    if not before.channel and after.channel:
        try:
            filename = await jtalk(username +"さんこんにちは！")
            enqueue(member.guild.voice_client, member.guild,
                    discord.FFmpegPCMAudio(filename), filename)
        except Exception as e:
            print(f"Failed to play greeting: {e}")
    if before.channel and not after.channel:
        try:
            filename = await jtalk(username + "さんが退出しました")
            enqueue(member.guild.voice_client, member.guild,
                    discord.FFmpegPCMAudio(filename), filename)
        except Exception as e:
            print(f"Failed to play farewell: {e}")
    allbot = True    
    selfcheck = False
    for mem in before.channel.members:
        if mem.id == bot.user.id:
            selfcheck = True
        if  not mem.bot:
            allbot = False
    if before.channel and allbot and selfcheck:
        client = member.guild.voice_client
        if client:
            # 自動退出時もキューをクリア
            if member.guild.id in queue_dict:
                queue_dict[member.guild.id].clear()
            await client.disconnect()
            await before.channel.send('ボイスチャンネルからログアウトしました')

async def cleanup_voice_clients():
    """Clean up all voice client connections"""
    for voice_client in bot.voice_clients:
        try:
            if voice_client.is_connected():
                await voice_client.disconnect(force=True)
        except Exception as e:
            print(f"Error disconnecting voice client: {e}")

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

def cleanup_all():
    """Clean up everything before shutdown"""
    # Clean up voice clients (run in the event loop if possible)
    try:
        if bot.loop and bot.loop.is_running():
            asyncio.run_coroutine_threadsafe(cleanup_voice_clients(), bot.loop).result(timeout=5)
        elif bot.loop:
            bot.loop.run_until_complete(cleanup_voice_clients())
    except Exception as e:
        print(f"Error during voice client cleanup: {e}")

    # Clean up processes
    cleanup_processes()


# Register cleanup handlers
atexit.register(cleanup_all)
signal.signal(signal.SIGTERM, lambda signum, frame: cleanup_all())
signal.signal(signal.SIGINT, lambda signum, frame: cleanup_all())


async def main():
    # start the client
    try:
        print("Starting Discord bot...")
        print(f"Client ID: {client_id[:10]}..." if len(client_id) > 10 else "Client ID: [too short]")
        print(f"Application ID: {application_id}")
        print(f"Dictionary Channel ID: {dictID}")
        async with bot:
            await bot.start(client_id)
    except Exception as e:
        print(f"Bot startup failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        await cleanup_voice_clients()
        cleanup_processes()


if __name__ == "__main__":
    asyncio.run(main())
