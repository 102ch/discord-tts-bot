# -*- coding: utf-8 -*-
import os
import json
import time
import uuid
import subprocess
import signal
import atexit
from celery import Celery
import redis

# Celery アプリケーション設定
celery_app = Celery('tts_worker')
celery_app.config_from_object({
    'broker_url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    'result_backend': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'task_routes': {
        'tts_worker.generate_tts_task': {'queue': 'tts_queue'},
    },
    'worker_prefetch_multiplier': 1,
    'task_acks_late': True,
})

# Redis クライアント
redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

# アクティブなプロセスを追跡
active_processes = set()

def cleanup_processes():
    """終了時にアクティブなプロセスをクリーンアップ"""
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

# クリーンアップハンドラーの登録
atexit.register(cleanup_processes)
signal.signal(signal.SIGTERM, lambda signum, frame: cleanup_processes())
signal.signal(signal.SIGINT, lambda signum, frame: cleanup_processes())

@celery_app.task(bind=True, max_retries=3)
def generate_tts_task(self, task_id, text, user_name, guild_id, channel_id):
    """
    バックグラウンドでTTS音声を生成するタスク
    """
    try:
        # 一意のファイル名を生成
        audio_dir = '/tmp/audio'
        os.makedirs(audio_dir, exist_ok=True)
        filename = f'{audio_dir}/{task_id}.wav'
        
        # OpenJTalk コマンドを構築
        open_jtalk = ['open_jtalk']
        mech = ['-x', '/var/lib/mecab/dic/open-jtalk/naist-jdic']
        htsvoice = ['-m', '/usr/share/hts-voice/mei/mei_normal.htsvoice']
        pitch = ['-fm', '-5']
        speed = ['-r', '1.0']
        outwav = ['-ow', filename]
        cmd = open_jtalk + mech + htsvoice + pitch + speed + outwav
        
        # プロセス実行
        process = subprocess.Popen(
            cmd, 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        
        active_processes.add(process)
        
        try:
            stdout, stderr = process.communicate(input=text.encode(), timeout=30)
            
            if process.returncode != 0:
                raise Exception(f"OpenJTalk failed: {stderr.decode()}")
            
            # ファイルサイズチェック (10MB制限)
            if os.path.getsize(filename) > 10000000:
                os.remove(filename)
                raise Exception("Generated audio file is too large")
            
            # 音声ファイル情報をRedisに保存
            audio_info = {
                'filename': filename,
                'task_id': task_id,
                'guild_id': str(guild_id),
                'channel_id': str(channel_id),
                'created_at': time.time(),
                'text': text[:50] + '...' if len(text) > 50 else text  # デバッグ用
            }
            
            # 5分間のTTLでRedisに保存
            redis_client.setex(f"audio:{task_id}", 300, json.dumps(audio_info))
            
            # ギルドの音声キューに追加
            redis_client.lpush(f"audio:queue:{guild_id}", task_id)
            
            print(f"TTS generated successfully: {task_id} for guild {guild_id}")
            return filename
            
        finally:
            active_processes.discard(process)
            
    except subprocess.TimeoutExpired:
        process.kill()
        if os.path.exists(filename):
            os.remove(filename)
        raise Exception("TTS generation timeout")
        
    except Exception as exc:
        # ファイルが存在する場合は削除
        if 'filename' in locals() and os.path.exists(filename):
            os.remove(filename)
        
        print(f"TTS generation failed for task {task_id}: {exc}")
        
        # 再試行
        if self.request.retries < self.max_retries:
            self.retry(countdown=60 * (self.request.retries + 1), exc=exc)
        else:
            # 最大再試行回数に達した場合、エラー情報をRedisに保存
            error_info = {
                'task_id': task_id,
                'error': str(exc),
                'failed_at': time.time()
            }
            redis_client.setex(f"error:{task_id}", 300, json.dumps(error_info))
            raise exc

@celery_app.task
def cleanup_old_audio_files():
    """
    古い音声ファイルをクリーンアップする定期タスク
    """
    audio_dir = '/tmp/audio'
    if not os.path.exists(audio_dir):
        return
    
    current_time = time.time()
    cleaned_count = 0
    
    for filename in os.listdir(audio_dir):
        file_path = os.path.join(audio_dir, filename)
        try:
            # 1時間以上古いファイルを削除
            if os.path.getmtime(file_path) < current_time - 3600:
                os.remove(file_path)
                cleaned_count += 1
        except Exception as e:
            print(f"Failed to cleanup file {file_path}: {e}")
    
    print(f"Cleaned up {cleaned_count} old audio files")
    return cleaned_count

if __name__ == '__main__':
    celery_app.start()