# -*- coding: utf-8 -*-
import json
import discord
import os
import re
import subprocess
from pydub import AudioSegment
import time
from threading import Timer
from pymongo import MongoClient
from datetime import datetime
from collections import defaultdict, deque
import random

queue_dict = defaultdict(deque)



def enqueue(voice_client, guild, source,filename):
    queue = queue_dict[guild.id]
    queue.append([source,filename])
    if not voice_client.is_playing():
        play(voice_client, queue)


def play(voice_client, queue):
    if not queue or voice_client.is_playing():
        return
    source = queue.popleft()
    # os.remove(source[1])
    voice_client.play(source[0], after=lambda e: play(voice_client, queue))


def current_milli_time():
    return round(time.time() * 1000)

async def addDict(arg1,arg2):
    with open('dict.txt', mode='a') as f:
        f.write(arg1 + ',' + arg2+'\n')

async def addDict(arg1, arg2):
    with open('dict.txt', mode='a') as f:
        f.write(arg1 + ',' + arg2+'\n')


class CommonModule:
    def load_json(self, file):
        with open(file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        return json_data

def replaceDict(text):
    f = open('dict.txt', 'r')
    lines = f.readlines()
    print(lines)

    for line in lines:
        pattern = line.strip().split(',')
        if pattern[0] in text and len(pattern) >= 2:
            text = text.replace(pattern[0], pattern[1])
    f.close()
    return text

def showDict():
    f = open('dict.txt', 'r')
    lines = f.readlines()
    output = "現在登録されている辞書一覧\n"
    for index, line in enumerate(lines):
        pattern = line.strip().split(',')
        output += "{0}: {1} -> {2}\n".format(index+1,pattern[0],pattern[1])
    f.close()
    return output

async def removeDict(num):
    try:
        cmd = ["sed", "-i.bak","-e", ("{0}d").format(num),"dict.txt"]
        subprocess.call(cmd)
    except Exception as e:
        print(e)
        return 0
    return 1

def replaceDict(text):
    f = open('dict.txt', 'r')
    lines = f.readlines()
    print(lines)

    for line in lines:
        pattern = line.strip().split(',')
        if pattern[0] in text and len(pattern) >= 2:
            text = text.replace(pattern[0], pattern[1])
    f.close()
    return text


def showDict():
    f = open('dict.txt', 'r')
    lines = f.readlines()
    output = "現在登録されている辞書一覧\n"
    for index, line in enumerate(lines):
        pattern = line.strip().split(',')
        output += "{0}: {1} -> {2}\n".format(index+1, pattern[0], pattern[1])
    f.close()
    return output


async def removeDict(num):
    try:
        cmd = ["sed", "-i.bak", "-e", ("{0}d").format(num), "dict.txt"]
        subprocess.call(cmd)
    except Exception as e:
        print(e)
        return 0
    return 1


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
currentChannel = None

url = re.compile('^http')
mention = re.compile('<@[^>]*>*')

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
        print(userId)
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
    global currentChannel

    if voice is True and volume is None:
        source = discord.PCMVolumeTransformer(voice.source)
        volume = source.volume

    if client.user != message.author:
        text = message.content
        print( message.channel,currentChannel)
        if text == '!join':
            channel = message.author.voice.channel
            currentChannel = message.channel
            voice = await channel.connect()
            await message.channel.send('ボイスチャンネルにログインしました')
        elif text == '!dc':
            await voice.disconnect()
            currentChannel = None
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
        elif text == '!get':
            await message.channel.send(showDict())
        elif re.match('^!add', text):
            args = message.content.split(" ")
            if len(args) < 3:
                await message.channel.send("Usage: !add A B")
                return
            a = args[1]
            b = args[2]
            if re.match('[k1h]',a):
                await message.channel.send("k1hに対するいたずらは許されませんよ♡")
                return
            if len(a) > 10 or len(b) > 10:
                await message.channel.send("荒らしは許されませんよ♡")
                return
            await addDict(a,b)
            await message.channel.send(("{0}を{1}と読むように辞書に登録しました！").format(a,b))
        elif re.match('^!remove', text):
            args = message.content.split(" ")
            if len(args) < 3:
                await message.channel.send("Usage: !remove 3 5")
                return
            num = int(args[1])
            rand = int(args[2])
            if(rand!=random.randint(1,6)):
                await message.channel.send("残念はずれ！")
                return

            if await removeDict(num):
                await message.channel.send("削除しました")
            else:
                await message.channel.send("エラーが発生しました")
        elif message.channel == currentChannel:
            print(message.guild.voice_client is True)
            if message.guild.voice_client:
                print(message.author)
                if len(text) > 100:
                    await message.channel.send("文字数が長すぎるよ")
                    return
                if mention.search(text):
                    text = await replaceUserName(text)
                text = re.sub('#.*','',str(message.author)) + text
                text = re.sub('http.*', '', text)
                text = replaceDict(text)
                if len(text) > 100:
                    await message.channel.send("文字数が長すぎるよ")
                    return
                filename = await jtalk(text)
                print(os.path.getsize(filename))
                if os.path.getsize(filename) > 1000000:
                    await message.channel.send("再生時間が長すぎるよ")
                    return
                enqueue(message.guild.voice_client, message.guild,
                        discord.FFmpegPCMAudio(filename),filename)
                timer = Timer(3, os.remove, (filename, ))
                timer.start()
                # os.remove(filename)

@client.event
async def on_voice_state_update(
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState):

        if not before.channel and after.channel:
            filename = await jtalk(member.display_name + "さんこんにちは！")
            enqueue(member.guild.voice_client, member.guild,
                    discord.FFmpegPCMAudio(filename),filename)
            timer = Timer(3, os.remove, (filename, ))
            timer.start()
        if before.channel and not after.channel:
            filename = await jtalk(member.display_name + "さんが退出してしまいました、退出してしまいました。磯のせいです。あーあ")
            enqueue(member.guild.voice_client, member.guild,
                    discord.FFmpegPCMAudio(filename),filename)
            timer = Timer(3, os.remove, (filename, ))
            timer.start()

client.run(client_id)
