FROM python:3.13-bookworm
USER root

RUN apt-get update
RUN apt-get -y install locales && \
    localedef -f UTF-8 -i ja_JP ja_JP.UTF-8
RUN apt-get install -y vim less
RUN apt-get install -y \
    ffmpeg

RUN apt-get install -y mecab open-jtalk open-jtalk-mecab-naist-jdic wget unzip pip
RUN wget http://sourceforge.net/projects/mmdagent/files/MMDAgent_Example/MMDAgent_Example-1.7/MMDAgent_Example-1.7.zip
RUN unzip MMDAgent_Example-1.7.zip
RUN cp -r MMDAgent_Example-1.7/Voice/ /usr/share/hts-voice/

ENV LANG ja_JP.UTF-8
ENV LANGUAGE ja_JP:ja
ENV LC_ALL ja_JP.UTF-8
ENV TZ JST-9
ENV TERM xterm

RUN mkdir -p /root/src
COPY requirements.txt /root/src
COPY . /root/src
WORKDIR /root/src
# 既存のvenvを削除
RUN rm -rf /root/src/.venv
ENV POETRY_HOME=/opt/poetry
RUN curl -sSL https://install.python-poetry.org | python3 && \
    cd /usr/local/bin && \
    ln -s /opt/poetry/bin/poetry && \
    poetry config virtualenvs.create false

RUN poetry install --no-interaction

CMD ["poetry" , "run", "python3", "app.py"]
