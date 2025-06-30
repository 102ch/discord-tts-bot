# Discord TTS Bot - キューイングシステム改善提案

## 現在のアーキテクチャの問題点

### 1. 同期処理によるボトルネック
- **OpenJTalk TTS生成**: `jtalk()`関数が同期的にsubprocessを実行しているため、メッセージが多い場合にレスポンスが遅延
- **ファイルI/O**: WAVファイルの作成・削除が同期処理で行われている
- **ブロッキング処理**: 複数のギルドで同時に多くのメッセージが投稿されると、全体のパフォーマンスが低下

### 2. メモリベースキューの限界
```python
queue_dict = defaultdict(deque)  # メモリ内キュー
```
- ボット再起動時にキューが消失
- スケーリング時に状態共有ができない
- メモリ使用量の制御が困難

### 3. リソース管理の課題
- OpenJTalkプロセスの管理が複雑
- 一時ファイルの削除タイミングが不安定
- 高負荷時のリソース枯渇リスク

## 提案: Redis + Celery による改善アーキテクチャ

### アーキテクチャ概要
```
Discord Bot (Main Process)
    ↓ メッセージ受信
Redis Queue (Task Queue)
    ↓ TTS生成タスク配信
Celery Workers (Background Processing)
    ↓ 音声ファイル生成
Redis Cache (Audio File Storage)
    ↓ 音声データ取得
Discord Bot (Audio Playback)
```

### 1. 非同期TTS生成システム

#### 現在の処理フロー
```python
async def on_message(message):
    text, filename = await text_check(text, user_name)  # 同期でTTS生成
    enqueue(voice_client, guild, discord.FFmpegPCMAudio(filename), filename)
```

#### 改善後の処理フロー
```python
# Bot側 - タスクをキューに送信
async def on_message(message):
    task_id = str(uuid.uuid4())
    tts_task.delay(task_id, text, user_name, guild_id, channel_id)
    
# Worker側 - バックグラウンドでTTS生成
@celery_app.task
def tts_task(task_id, text, user_name, guild_id, channel_id):
    filename = generate_tts(text)
    redis_client.set(f"audio:{task_id}", filename, ex=300)
    notify_audio_ready.delay(task_id, guild_id, channel_id)
```

### 2. Redis構成設計

#### キー設計
```
# TTS タスクキュー
tts:queue:{guild_id}        # ギルド毎のタスクキュー
tts:processing:{task_id}    # 処理中タスクの状態
tts:audio:{task_id}         # 生成された音声ファイルパス

# 音声再生キュー  
audio:queue:{guild_id}      # ギルド毎の再生キュー
audio:playing:{guild_id}    # 現在再生中の情報

# 設定・辞書データ
dict:{guild_id}             # ギルド辞書データ
user:nickname:{user_id}     # ユーザーニックネーム
```

#### データ構造例
```json
{
  "task_id": "uuid-string",
  "text": "処理対象テキスト", 
  "user_name": "ユーザー名",
  "guild_id": "123456789",
  "channel_id": "987654321",
  "priority": 1,
  "created_at": "2024-01-01T12:00:00Z"
}
```

### 3. 実装案

#### 必要な依存関係追加
```toml
# pyproject.toml
dependencies = [
    "discord.py[voice]==2.3.2",
    "pydub",
    "redis>=4.5.0",
    "celery>=5.3.0",
    "redis[hiredis]",  # パフォーマンス向上
]
```

#### Docker Compose拡張
```yaml
version: "3.1"

services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  app:
    build: ./app
    tty: true
    environment:
      - DISCORD_CLIENT_ID=${DISCORD_CLIENT_ID}
      - DISCORD_APP_ID=${DISCORD_APP_ID}
      - DICT_CH_ID=${DICT_CH_ID}
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./app:/root/src
    depends_on:
      - redis

  celery_worker:
    build: ./app
    command: celery -A tts_worker worker --loglevel=info --concurrency=4
    environment:
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./app:/root/src
      - shared_audio:/tmp/audio
    depends_on:
      - redis

volumes:
  redis_data:
  shared_audio:
```

### 4. コード改善例

#### TTS Worker (新規ファイル: tts_worker.py)
```python
from celery import Celery
import redis
import subprocess
import uuid
import os

celery_app = Celery('tts_worker')
celery_app.config_from_object({
    'broker_url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    'result_backend': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
})

redis_client = redis.from_url(os.getenv('REDIS_URL'))

@celery_app.task(bind=True, max_retries=3)
def generate_tts_task(self, task_id, text, user_name, guild_id, channel_id):
    try:
        filename = f'/tmp/audio/{task_id}.wav'
        
        # OpenJTalk実行
        open_jtalk = ['open_jtalk']
        mech = ['-x', '/var/lib/mecab/dic/open-jtalk/naist-jdic']
        htsvoice = ['-m', '/usr/share/hts-voice/mei/mei_normal.htsvoice']
        pitch = ['-fm', '-5']
        speed = ['-r', '1.0']
        outwav = ['-ow', filename]
        cmd = open_jtalk + mech + htsvoice + pitch + speed + outwav
        
        result = subprocess.run(cmd, input=text.encode(), 
                              capture_output=True, timeout=30)
        
        if result.returncode != 0:
            raise Exception(f"OpenJTalk failed: {result.stderr.decode()}")
        
        # 音声ファイル情報をRedisに保存
        audio_info = {
            'filename': filename,
            'task_id': task_id,
            'guild_id': guild_id,
            'channel_id': channel_id,
            'created_at': time.time()
        }
        redis_client.setex(f"audio:{task_id}", 300, json.dumps(audio_info))
        
        # 再生キューに追加
        redis_client.lpush(f"audio:queue:{guild_id}", task_id)
        
        return filename
        
    except Exception as exc:
        self.retry(countdown=60, exc=exc)
```

#### Bot側の改修 (app.py の主要変更点)
```python
import redis
from celery import Celery

# Redis接続
redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

# Celeryクライアント
celery_app = Celery('discord_bot')
celery_app.config_from_object({
    'broker_url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
})

async def on_message(message: discord.Message):
    # ... 既存のチェック処理 ...
    
    # TTS生成をバックグラウンドタスクに送信
    task_id = str(uuid.uuid4())
    celery_app.send_task('tts_worker.generate_tts_task', 
                        args=[task_id, text, user_name, 
                              message.guild.id, message.channel.id])
    
    # 音声キューの監視を開始
    asyncio.create_task(monitor_audio_queue(message.guild.id, message.channel.id))

async def monitor_audio_queue(guild_id, channel_id):
    """音声キューを監視して準備できた音声を再生"""
    while True:
        task_id = redis_client.brpop(f"audio:queue:{guild_id}", timeout=1)
        if task_id:
            audio_info = redis_client.get(f"audio:{task_id[1].decode()}")
            if audio_info:
                data = json.loads(audio_info)
                voice_client = get_voice_client(channel_id)
                if voice_client:
                    enqueue_local(voice_client, guild_id, data['filename'])
        await asyncio.sleep(0.1)
```

## 期待される効果

### 1. パフォーマンス向上
- **応答性**: メッセージ受信時の即座のレスポンス
- **並行処理**: 複数ギルドでの同時TTS生成
- **リソース効率**: CPUリソースの有効活用

### 2. 可用性・信頼性向上
- **障害耐性**: Worker障害時の自動復旧
- **データ永続化**: Redisによるキュー状態の保持
- **水平スケーリング**: Worker数の動的調整

### 3. 運用面の改善
- **監視**: Redis/Celeryの豊富な監視ツール
- **デバッグ**: タスクの実行状況追跡
- **メンテナンス**: ローリングアップデート対応

## 実装優先度

### Phase 1: 基盤構築
1. Redis + Celery環境構築
2. TTS生成のワーカー化
3. 基本的なキューイング実装

### Phase 2: 最適化
1. 優先度制御の実装
2. 音声ファイルキャッシュ最適化
3. エラーハンドリング強化

### Phase 3: 監視・運用
1. 監視ダッシュボード構築
2. パフォーマンス指標収集
3. 自動スケーリング対応

この改善により、現在の同期処理による遅延問題が解消され、より多くのユーザーに安定したTTSサービスを提供できるようになります。