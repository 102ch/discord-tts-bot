import json
import discord
import os
import re
import subprocess
from pydub import AudioSegment
import time

from collections import defaultdict, deque

queue_dict = defaultdict(deque)


def enqueue(voice_client, guild, source):
    queue = queue_dict[guild.id]
    queue.append(source)
    if not voice_client.is_playing():
        play(voice_client, queue)


def play(voice_client, queue):
    if not queue or voice_client.is_playing():
        return
    source = queue.popleft()
    voice_client.play(source, after=lambda e: play(voice_client, queue))


def current_milli_time():
    return round(time.time() * 1000)


class CommonModule:
    def load_json(self, file):
        with open(file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        return json_data


async def jtalk(t):
    open_jtalk = ['open_jtalk']
    mech = ['-x', '/var/lib/mecab/dic/open-jtalk/naist-jdic']
    htsvoice = ['-m', '/usr/share/hts-voice/mei/mei_normal.htsvoice']
    pitch = ['-fm', '-5']
    speed = ['-r', '1.0']
    file = str(current_milli_time())
    outwav = ['-ow', file + '.wav']
    cmd = open_jtalk+mech+htsvoice+pitch+speed+outwav
    c = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    c.stdin.write(t.encode())
    c.stdin.close()
    c.wait()
    return file + '.wav'

client = discord.Client()
client_id = os.environ['DISCORD_CLIENT_ID']
voice = None
volume = None

url = re.compile('^http')
mention = re.compile('<@![^>]*>*')

# GUILD_ID=833346660201398282
# guild = client.get_guild(GUILD_ID)


@client.event
async def on_ready():
    # 起動時の処理
    print('Bot is wake up.')


async def replaceUserName(text):
    for word in text.split():
        if not mention.match(word):
            continue
        userId = re.sub('[<@!> ]', '', word)
        # print(userId)
        userName = str(await client.fetch_user(userId))
        # nickName = str(await guild.get_member_named(userName))
        # print(nickName)
        # userName = '砂糖#'
        userName = re.sub('#.*', '', userName)
        text = text.replace(word, '@'+userName)
    return text


@client.event
async def on_message(message):
    # テキストチャンネルにメッセージが送信されたときの処理
    global voice, volume, read_mode
    volume = 0.5

    if voice is True and volume is None:
        source = discord.PCMVolumeTransformer(voice.source)
        volume = source.volume

    if client.user != message.author:
        text = message.content
        if text == '!join':
            channel = message.author.voice.channel
            voice = await channel.connect()
            await message.channel.send('ボイスチャンネルにログインしました')
        elif text == '!dc':
            await voice.disconnect()
            await message.channel.send('ボイスチャンネルからログアウトしました')
        elif text == '!status':
            if voice.is_connected():
                await message.channel.send('ボイスチャンネルに接続中です')
        elif text == '!volume_up':
            volume = volume + 0.1
            await message.channel.send('音量を上げました')
        elif text == '!volume_down':
            volume = volume - 0.1
            await message.channel.send('音量を下げました')
        elif text == '!bye':
            await client.close()
        else:
            print(text)
            if mention.search(text):
                text = await replaceUserName(text)
            if url.match(text):
                return
            filename = await jtalk(text)
            enqueue(message.guild.voice_client, message.guild,
                    discord.FFmpegPCMAudio(filename))
            # os.remove(filename)

client.run(client_id)
