# Speech pipeline

Linux python project to:
* recognize human speech (German or English), from either a microphone or a video
* then translate it to English or German
* then convert it into speech (text-to-speech)

## Installation

Tested on Ubuntu 22.04.1 LTS with Python 3.10.4 and pip 22.2.2

* Clone and change to the repository and `bash install.sh`
* Confirm the installation of the programs it needs
* Activate the [virtual environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/) `source ~/venv_speech_pipeline/bin/activate`

## Models

All machine learning models will automatically be downloaded:
* [Vosk](https://alphacephei.com/vosk/) models in `~/.cache/vosk/` (more than 1 GB each)
* [Marian](https://huggingface.co/docs/transformers/model_doc/marian) models in working/git directory
* [TTS](https://github.com/coqui-ai/TTS) models in `~/.local/share/tts/`

## Usage

### From a file

Run `python3 process_speech.py -h` for more information

### From a microphone

Run `python3 process_speech.py -h` for more information
