FROM ubuntu

# セキュリティ向上のため非rootユーザーを作成
RUN groupadd -r botuser && useradd -r -g botuser botuser

# システムの更新とパッケージインストール
RUN apt-get update && apt-get install -y \
    locales \
    vim \
    less \
    ffmpeg \
    mecab \
    open-jtalk \
    open-jtalk-mecab-naist-jdic \
    hts-voice-nitech-jp-atr503-m001 \
    python3 \
    python3-pip \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 日本語ロケールの設定
RUN localedef -f UTF-8 -i ja_JP ja_JP.UTF-8

# 音声ファイルのダウンロードと設置
RUN wget http://sourceforge.net/projects/mmdagent/files/MMDAgent_Example/MMDAgent_Example-1.7/MMDAgent_Example-1.7.zip \
    && unzip MMDAgent_Example-1.7.zip \
    && cp -r MMDAgent_Example-1.7/Voice/mei/ /usr/share/hts-voice/ \
    && rm -rf MMDAgent_Example-1.7* \
    && chmod -R 755 /usr/share/hts-voice/

# 環境変数の設定
ENV LANG ja_JP.UTF-8
ENV LANGUAGE ja_JP:ja
ENV LC_ALL ja_JP.UTF-8
ENV TZ JST-9
ENV TERM xterm

# アプリケーション用ディレクトリの作成
RUN mkdir -p /app /app/temp && chown -R botuser:botuser /app

# 作業ディレクトリの設定
WORKDIR /app

# 依存関係ファイルのコピーとインストール
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools && \
    python3 -m pip install --no-cache-dir -r requirements.txt

# アプリケーションファイルのコピー
COPY . .
RUN chown -R botuser:botuser /app

# 非rootユーザーに切り替え
USER botuser

CMD ["python3", "app.py"]
