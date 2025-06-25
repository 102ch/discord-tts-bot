FROM ubuntu:22.04
USER root

# Set environment variables
ENV LANG=ja_JP.UTF-8
ENV LANGUAGE=ja_JP:ja
ENV LC_ALL=ja_JP.UTF-8
ENV TZ=JST-9
ENV TERM=xterm
ENV DEBIAN_FRONTEND=noninteractive

# Update and install system dependencies
RUN apt-get update && apt-get install -y \
    locales \
    vim \
    less \
    ffmpeg \
    mecab \
    open-jtalk \
    open-jtalk-mecab-naist-jdic \
    hts-voice-nitech-jp-atr503-m001 \
    wget \
    unzip \
    curl \
    software-properties-common \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set up locale
RUN localedef -f UTF-8 -i ja_JP ja_JP.UTF-8

# Install voice data
RUN wget http://sourceforge.net/projects/mmdagent/files/MMDAgent_Example/MMDAgent_Example-1.7/MMDAgent_Example-1.7.zip \
    && unzip MMDAgent_Example-1.7.zip \
    && cp -r MMDAgent_Example-1.7/Voice/mei/ /usr/share/hts-voice/ \
    && rm -rf MMDAgent_Example-1.7.zip MMDAgent_Example-1.7

# Install Python 3.12
RUN add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y python3.12 python3.12-venv python3.12-dev \
    && rm -rf /var/lib/apt/lists/*

# Install uv using official installer
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Create working directory
RUN mkdir -p /root/src
WORKDIR /root/src

# Copy project files
COPY pyproject.toml ./

# Install dependencies using uv with Python 3.12
RUN uv sync --python 3.12

# Copy application code
COPY . .

# Run the application
CMD ["uv", "run", "--python", "3.12", "python3", "app.py"]
