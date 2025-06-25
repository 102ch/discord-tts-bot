# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Discord Text-to-Speech bot that reads Japanese chat messages aloud in voice channels using OpenJTalk voice synthesis. The bot is containerized and designed to run in Japanese Discord servers.

## Development Commands

**Start development environment:**
```bash
docker-compose up --build
```

**Run production version:**
```bash
docker-compose -f docker-compose-release.yml up
```

**Direct Python execution (requires manual dependency setup):**
```bash
cd app
python3 app.py
```

## Environment Setup

Copy environment template and configure Discord credentials:
```bash
cp .env.default .env
# Edit .env to add DISCORD_CLIENT_ID and DISCORD_APP_ID
```

## Architecture

**Main Application:** `app/app.py` - Single-file Discord bot implementation with slash commands, voice synthesis, and audio queue management.

**Container Architecture:** Ubuntu-based container with Japanese locale, OpenJTalk, MeCab, and MEI voice model pre-installed.

**Dictionary System:** Custom pronunciations are stored as Discord messages rather than in a database, accessed via channel message history.

**Audio Pipeline:** Text → MeCab tokenization → OpenJTalk synthesis → pydub processing → Discord voice playback with per-guild queuing.

## Key Components

- **Voice Connection Management:** Join/leave voice channels with automatic disconnect when empty
- **Text Processing:** URL removal, emoji/mention filtering, Japanese text normalization
- **Custom Dictionary:** User-defined pronunciations stored in Discord channel messages
- **Audio Queue:** Thread-based per-guild audio playback system
- **Volume Control:** Runtime audio volume adjustment

## Discord Bot Commands

- `/join` - Connect to voice channel and start reading messages
- `/dc` - Disconnect from voice channel  
- `/add [word] [pronunciation]` - Add custom pronunciation
- `/remove [number]` - Remove dictionary entry
- `/volume up/down` - Adjust playback volume
- `/rename [name]` - Set custom TTS nickname

## Dependencies

**Core:** discord.py[voice], pydub
**System:** OpenJTalk, MeCab, FFmpeg, MEI voice model
**Container:** Multi-architecture builds for linux/amd64 and linux/arm64

## CI/CD

GitHub Actions automatically builds and publishes container images to GHCR on master branch pushes with multi-architecture support.