# feat: Redis + Celery による非同期TTS処理システムの実装

## 🚀 主な変更

### アーキテクチャの大幅改善
- **同期処理 → 非同期処理**: OpenJTalk TTS生成をバックグラウンドワーカーに移行
- **メモリキュー → Redis**: 永続的で信頼性の高いタスクキューシステム
- **単一プロセス → 分散処理**: Celeryワーカーによる水平スケーリング対応

### 新規追加ファイル
- `app/tts_worker.py`: Celeryワーカーによる非同期TTS生成
- `app/celerybeat_schedule.py`: 定期クリーンアップタスクの設定
- `.env.sample`: 更新された環境変数テンプレート

### 修正されたファイル
- `app/app.py`: 非同期処理対応、Redis連携、ギルド別データ管理
- `app/pyproject.toml`: Redis/Celery依存関係追加
- `docker-compose.yaml`: Redis、Celeryワーカー、Beat scheduler追加
- `README.md`: 新アーキテクチャの詳細説明

## 📈 パフォーマンス改善効果

### 応答性向上
- メッセージ受信時の即座のレスポンス（TTS生成待機なし）
- 複数ギルドでの並行処理対応

### 信頼性向上  
- Redis による永続キューとタスク状態管理
- ワーカー障害時の自動復旧機能
- 音声ファイルの自動クリーンアップ

### スケーラビリティ
- 水平スケーリング対応（ワーカー数調整）
- ギルド別の独立した辞書・設定管理
- リソース効率的な処理分散

## 🔧 技術仕様

### Redis キー設計
```
tts:queue:{guild_id}        # TTS生成タスクキュー
audio:queue:{guild_id}      # 音声再生キュー  
audio:{task_id}             # 生成された音声情報
dict:{guild_id}             # ギルド別辞書データ
user:nickname:{guild_id}    # ユーザーニックネーム
```

### Celery タスク
- `generate_tts_task`: 非同期TTS音声生成
- `cleanup_old_audio_files`: 定期的な古いファイル削除

### 下位互換性
- 既存のメモリベースキューとの併用サポート
- 段階的移行可能な設計

## 🚦 実行方法

```bash
# 全サービス起動
docker-compose up --build

# 個別起動
docker-compose up redis           # Redis のみ
docker-compose up app            # Discord Bot のみ  
docker-compose up celery_worker  # TTS ワーカーのみ
```

この実装により、高負荷時でも安定したTTSサービスの提供が可能になります。