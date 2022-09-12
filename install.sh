#!/bin/bash
# Clone https://github.com/codemmmmm/speech_pipeline.git
# Switch to branch read_from_video 'git checkout read_from_video'

# running as root creates the venv in /root and maybe does more bad stuff
if [ "$EUID" -eq 0 ]
  then echo "Please don't run as root."
  exit
fi

venv_name="venv_speech_pipeline"
sudo apt-get update && sudo apt-get install python3-venv ffmpeg mpv espeak-ng curl
echo "Creating python venv $HOME/$venv_name"
python3 -m venv $HOME/$venv_name
source $HOME/$venv_name/bin/activate
pip3 install --upgrade pip
pip3 install wheel
pip3 install -r requirements.txt

python3 recognize_stream.py --help
normal=$(tput sgr0)
green=$(tput setaf 2)
echo "Try: $green python3 recognize_stream.py --in-language de tagesschau.mp4 $normal"
echo "You have to activate the virtual environment: $green source $HOME/$venv_name/bin/activate $normal"