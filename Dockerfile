FROM ubuntu:latest
RUN apt-get update && \
    apt-get install -y alsa-base alsa-utils pulseaudio pulseaudio-utils python3-pip
RUN pip3 install torch==1.9.0+cpu torchvision==0.10.0+cpu torchaudio==0.9.0 -f https://download.pytorch.org/whl/torch_stable.html
RUN pip3 install vosk transformers sentencepiece pyttsx3
RUN apt-get install -y ffmpeg espeak pavucontrol
COPY recognize_stream.py download_model.py /recognizer/
COPY model /recognizer/model 
COPY beguiling-drafter-2018-08-30 /recognizer/beguiling-drafter-2018-08-30
WORKDIR /recognizer
RUN python3 download_model.py
ENTRYPOINT ["python3", "recognize_stream.py"]
#https://askubuntu.com/questions/972510/how-to-set-alsa-default-device-to-pulseaudio-sound-server-on-docker
# docker run -it \
#     --device /dev/snd \
#     -e PULSE_SERVER=unix:${XDG_RUNTIME_DIR}/pulse/native \
#     -v ${XDG_RUNTIME_DIR}/pulse/native:${XDG_RUNTIME_DIR}/pulse/native \
#     -v ~/.config/pulse/cookie:/root/.config/pulse/cookie \
#     --group-add $(getent group audio | cut -d: -f3) \
#     mmdockermmmm/stream_recognizer:latest

#-e set environment variable
#--group-add runs "as" audio group