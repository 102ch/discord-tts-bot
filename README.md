# discord-tts-bot

OpenJTalkを用いてDiscordのチャットに投稿されたメッセージをVoice Chatで読み上げるBotです。

## セットアップ

### 環境変数の設定

環境変数のサンプルファイルを用意しているので、以下を実行してください：

```bash
cp .env.sample .env
```

次に、`.env`ファイルを編集して以下の値を設定してください：
- `DISCORD_CLIENT_ID`: DiscordのBotのクライアントID
- `DISCORD_APP_ID`: DiscordのBotのAPPLICATION ID  
- `DICT_CH_ID`: 辞書データを保存するチャンネルのID

DiscordのBotトークンとApplication IDは [Discord Developer Portal](https://discord.com/developers/applications) で取得できます。

### Dockerを使った開発

`docker-compose.yaml`を利用して開発を行えます。

`docker-compose up --build`で立ち上げるとビルドした上で起動してくれます。

### Dev Containerを使った開発

`Reopen in Container`を選択するとDev Containerを利用できます。

コードを起動する際には、以下のいずれかを実行してください：
- `app/app.py` (元のバージョン)  
- `app/app_improved.py` (改善版、推奨)

## Discord Botの使い方

以下のスラッシュコマンドが利用できます：

```
/join : ボイスチャンネルに参加します
/dc : ボイスチャンネルから退出します  
/status : 現在のステータスを確認します
/volume : 音量を調整します (up/down)
/get : 辞書の内容を表示します
/add : 辞書に新しい単語を登録します
/remove : 辞書から単語を削除します
/rename : あなたの呼び方を設定します
/bye : Botを終了します
```

## 改善点 (v2.0)

### セキュリティの向上
- Dockerコンテナを非rootユーザーで実行
- 環境変数の安全な管理
- 入力サニタイゼーションの改善
- ファイルシステムの読み取り専用化

### コード品質の向上  
- クラスベース設計への移行
- グローバル変数の削除
- 適切なエラーハンドリング
- 型ヒントの追加
- ログ機能の実装

### 機能の改善
- カスタム例外による詳細なエラー報告
- 設定ファイルの分離
- 非同期処理の最適化
- 一時ファイルの適切な管理
