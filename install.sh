#!/bin/bash
# Clone https://github.com/codemmmmm/speech_pipeline.git
# Switch to branch read_from_video 'git checkout read_from_video'


venv_name="venv_speech_pipeline"
sudo apt update && sudo apt install python3.10-venv ffmpeg mpv espeak-ng curl
echo "Creating python venv $HOME/$venv_name"
python3 -m venv $HOME/$venv_name
source $HOME/$venv_name/bin/activate
pip3 install -r requirements.txt

python3 recognize_stream.py --help
normal=$(tput sgr0)
green=$(tput setaf 2)
echo "Try: $green python3 recognize_stream.py --in-language de tagesschau.mp4 $normal"