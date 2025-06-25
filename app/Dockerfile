FROM ubuntu
USER root

RUN apt-get update
RUN apt-get -y install locales && \
    localedef -f UTF-8 -i ja_JP ja_JP.UTF-8
RUN apt-get install -y vim less
RUN apt-get install -y \
    ffmpeg

RUN apt-get install -y mecab open-jtalk open-jtalk-mecab-naist-jdic hts-voice-nitech-jp-atr503-m001 python3 wget unzip pip
RUN wget http://sourceforge.net/projects/mmdagent/files/MMDAgent_Example/MMDAgent_Example-1.7/MMDAgent_Example-1.7.zip
RUN unzip MMDAgent_Example-1.7.zip
RUN cp -r MMDAgent_Example-1.7/Voice/mei/ /usr/share/hts-voice/

ENV LANG ja_JP.UTF-8
ENV LANGUAGE ja_JP:ja
ENV LC_ALL ja_JP.UTF-8
ENV TZ JST-9
ENV TERM xterm

RUN mkdir -p /root/src
COPY requirements.txt /root/src
COPY . /root/src
WORKDIR /root/src

RUN python3 -m pip install --upgrade setuptools --break-system-packages
RUN python3 -m pip install -r requirements.txt --break-system-packages

CMD ["python3","app.py"]
