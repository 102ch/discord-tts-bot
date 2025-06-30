# discord-tts-bot

OpenJTalkを用いてDiscordのチャットに投稿されたメッセージをVoice Chatで読み上げるBotです。

## 🚀 新機能: 非同期TTS処理

このボットは**Redis + Celery**アーキテクチャにより、高性能な非同期TTS処理を実現しています。

### 主な改善点
- **非同期処理**: メッセージ受信時の即座のレスポンス
- **スケーラブル**: 複数のワーカーで並行TTS生成
- **信頼性**: Redis による永続キューとタスク管理
- **ギルド別管理**: サーバーごとの独立した辞書・設定

## 開発者へ

環境変数のサンプルファイルを用意しているので、`cp .env.sample .env`を実行してください。

次に、以下の環境変数を設定してください：
- `DISCORD_TOKEN`: DiscordのBotのトークン
- `DISCORD_CLIENT_ID`: DiscordのBotのCLIENT ID  
- `DISCORD_APP_ID`: DiscordのBotのAPPLICATION ID
- `DICT_CH_ID`: 辞書データを保存するチャンネルID
- `REDIS_URL`: RedisのURL (デフォルト: `redis://localhost:6379/0`)

### Dockerを使った開発

`docker-compose up --build`で立ち上げると以下のサービスが起動します：
- **redis**: キューとデータストレージ
- **app**: メインのDiscord Bot
- **celery_worker**: バックグラウンドTTS処理ワーカー
- **celery_beat**: 定期タスク実行

### Dev Containerを使った開発

`Reopen in Container`を選択するとDev Containerを利用できます。

コードを起動する際には、`app/app.py`を実行してください。

## 🔧 アーキテクチャ

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

### 処理フロー
1. Discordメッセージ受信 → 即座にレスポンス
2. TTS生成タスクをRedisキューに送信
3. Celeryワーカーがバックグラウンドで音声生成
4. 生成完了時に自動的に音声再生キューに追加
5. Discord Botが順次音声を再生

## Discord Botの使い方

```
/join : VoiceChannelに入っている状態で実行すると，実行した場所のメッセージを読み上げます
/dc : ボイスチャンネルから退出します
/status : show status
/get : 辞書の内容を表示
/add [置換前] [置換後] : 辞書に単語を登録
/remove [番号] : 辞書から単語を削除
/rename [名前] : あなたの呼び方を設定
```

## 📊 監視・運用

### Redis監視
```bash
# キューの状態確認
redis-cli LLEN audio:queue:{guild_id}

# アクティブなタスク確認  
redis-cli KEYS "audio:*"
```

### Celery監視
```bash
# ワーカー状態確認
celery -A tts_worker inspect active

# タスク統計
celery -A tts_worker inspect stats
```
