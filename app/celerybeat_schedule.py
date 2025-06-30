# -*- coding: utf-8 -*-
from celery import Celery
from celery.schedules import crontab
import os

# Celery Beat 設定
celery_app = Celery('tts_worker')
celery_app.config_from_object({
    'broker_url': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    'result_backend': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'timezone': 'Asia/Tokyo',
    
    # 定期タスクのスケジュール設定
    'beat_schedule': {
        'cleanup-old-audio-files': {
            'task': 'tts_worker.cleanup_old_audio_files',
            'schedule': crontab(minute=0),  # 毎時0分に実行
        },
    },
})

if __name__ == '__main__':
    celery_app.start()