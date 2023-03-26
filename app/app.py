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

# from dotenv import load_dotenv
# load_dotenv()

queue_dict = defaultdict(deque)
connecting_channels = set()


def enqueue(voice_client: discord.VoiceClient, guild: discord.guild, source, filename: str):
    queue = queue_dict[guild.id]
    queue.append([source, filename])
    if not voice_client:
        return
    if not voice_client.is_playing():
        play(voice_client, queue)


def play(voice_client: discord.VoiceClient, queue: deque):
    if not queue or voice_client.is_playing():
        return
    source = queue.popleft()
    # os.remove(source[1])
    voice_client.play(source[0], after=lambda e: play(voice_client, queue))


def current_milli_time() -> int:
    return round(time.time() * 1000)


def addDict(arg1: str, arg2: str):
    with open('dict.txt', mode='a+') as f:
        f.write(arg1 + ',' + arg2 + '\n')

    with open("dict.txt", mode="r")as f:
        print(f.read())


def showDict() -> str:
    f = open('dict.txt', 'r')
    lines = f.readlines()
    print(lines)
    output = "現在登録されている辞書一覧\n"
    for index, line in enumerate(lines):
        pattern = line.strip().split(',')
        output += "{0}: {1} -> {2}\n".format(index + 1, pattern[0], pattern[1])
    f.close()
    return output


async def removeDict(num: int) -> bool:
    try:
        cmd = ["sed", "-i.bak", "-e", ("{0}d").format(num), "dict.txt"]
        subprocess.call(cmd)
    except Exception as e:
        print(e)
        return False
    return True


def replaceDict(text: str) -> str:
    if (not os.path.isfile('dict.txt')):
        open('dict.txt', 'w+').close()
    f = open('dict.txt', 'r+')
    lines = f.readlines()
    print(lines)
    for line in lines:
        pattern = line.strip().split(',')
        if pattern[0] in text and len(pattern) >= 2:
            text = text.replace(pattern[0], pattern[1])
    f.close()
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
    # file = str(current_milli_time())
    outwav = ['-ow', 'output.wav']
    cmd = open_jtalk + mech + htsvoice + pitch + speed + outwav
    c = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    c.stdin.write(t.encode())
    c.stdin.close()
    c.wait()
    return 'output.wav'


def get_voice_client(channel_id: int) -> discord.VoiceClient | None:
    for client in bot.voice_clients:
        if client.channel.id == channel_id:
            return client
    else:
        return None


async def text_check(text: str, user_name: str) -> str:
    print(text)
    if len(text) > 100:
        raise Exception("文字数が長すぎるよ")
    if stamp.search(text):
        text = replaceStamp(text)
    if mention.search(text):
        text = await replaceUserName(text)
    text = re.sub('#.*', '', str(user_name)) + ' ' + text
    text = re.sub('http.*', '', text)
    text = replaceDict(text)
    if len(text) > 100:
        raise Exception("文字数が長すぎるよ")
    filename = await jtalk(text)
    if os.path.getsize(filename) > 10000000:
        raise Exception("再生時間が長すぎるよ")
    return text, filename


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
    await tree.sync()
    with open("dict.txt", "w"):  # 起動時に空のdictを生成
        pass
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


@tree.command(name="get", description="辞書の内容を取得するよ")
async def get(interaction: discord.Interaction):
    await interaction.response.send_message(showDict())


@tree.command(name="add", description="辞書に新しい単語を登録するよ")
@discord.app_commands.describe(arg1="置換前の単語を入れてね", arg2="置換後の単語を入れてね")
async def add(interaction: discord.Interaction, arg1: str, arg2: str):
    if len(arg1) > 10 or len(arg2) > 10:
        return await interaction.response.send_message("荒らしは許されませんよ♡\n置換する単語は10文字儼にしてね")
    addDict(arg1, arg2)
    await interaction.response.send_message(f"{arg1}を{arg2}と読むように辞書に登録しました！")


@tree.command(name="remove", description="辞書の単語を削除するよ")
@discord.app_commands.describe(num="削除する単語の番号を入れてね")
async def remove(interaction: discord.Interaction, num: int):
    if await removeDict(num):
        await interaction.response.send_message("削除しました")
    else:
        await interaction.response.send_message("エラーが発生しました")


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

    try:
        text, filename = await text_check(text, message.author.name)
    except Exception as e:
        return await message.channel.send(e)

    if not message.guild.voice_client:
        return await bot.process_commands(message)

    enqueue(message.guild.voice_client, message.guild,
            discord.FFmpegPCMAudio(filename), filename)
    # timer = Timer(3, os.remove, (filename, ))
    # timer.start()
    # os.remove(filename)
    # コマンド側へメッセージ内容を渡す
    await bot.process_commands(message)


@bot.event
async def on_voice_state_update(
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState):

    # Chatに接続中でないなら処理しない
    global currentChannel
    if currentChannel is None:
        return

    if not before.channel and after.channel:
        filename = await jtalk(replaceDict(member.display_name + "さんこんにちは！"))
        enqueue(member.guild.voice_client, member.guild,
                discord.FFmpegPCMAudio(filename), filename)
        timer = Timer(3, os.remove, (filename, ))
        timer.start()
    if before.channel and not after.channel:
        filename = await jtalk(replaceDict(member.display_name + "さんが退出しました"))
        enqueue(member.guild.voice_client, member.guild,
                discord.FFmpegPCMAudio(filename), filename)
        timer = Timer(3, os.remove, (filename, ))
        timer.start()


async def main():
    # start the client
    async with bot:

        await bot.start(client_id)

asyncio.run(main())
