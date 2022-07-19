# Speech recognition

Linux python project to:
* convert human English speech, from either a file, a microphone or an application, to text
* then translate it to German 
* then convert it into speech (text-to-speech).

## Installation

### Native installation

Simply download the python files and all models (Vosk model, translation model, noise suppression model) into the same directory:
* Create and start a [virtual environment](https://packaging.python.org/guides/installing-using-pip-and-virtual-environments/).
* Install [Vosk](https://alphacephei.com/vosk/install)
* Download and unzip one of the English [Vosk models](https://alphacephei.com/vosk/models), [this](https://alphacephei.com/vosk/models/vosk-model-en-us-daanzu-20200905.zip) is recommended. Rename it to `model`.
* Install ffmpeg with the package manager of your choice.
* Install pytorch according to this [guide](https://pytorch.org/get-started/locally/) and the selector on the top of the page.
* Install [transformers](https://huggingface.co/transformers/installation.html).
* Install [sentencepiece](https://pypi.org/project/sentencepiece/).
* Run the download_model.py which downloads this [translation model](https://huggingface.co/Helsinki-NLP/opus-mt-en-de) into the `translate-en-de` directory.
* If you want to try the noise suppression filter, download and unzip [this model](https://github.com/GregorR/rnnoise-models/tree/master/beguiling-drafter-2018-08-30). The directory needs to be called `beguiling-drafter-2018-08-30`.
* Install espeak with the package manager of your choice.
* Install alsa-utils with the package manager of your choice.
* Install pavucontrol with the package manager of your choice.
* Install [TTS](https://pypi.org/project/TTS/).
* Install sox with the package manager of your choice. If it can't handle mp3 files install libmad on Archlinux (for Ubuntu libsox-fmt-mp3 might work).

### Docker container

Install PulseAudio on your device.

## Usage

### From a file

Run `python3 recognize.py file` to print the recognized speech.

Optional arguments:

* -h, --help

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print the help message and exit
* --f, --filter

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;use experimental noise suppression. Try this if you aren't satisfied with the result.

### From an audio stream

#### Native installation

Run `python3 recognize_stream.py` to print the recognized speech. It will print after a short period of not recognizing any speech input. Make sure your microphone doesn't pick up the text-to-speech output.

#### Docker container

Run `run.sh` to print the recognized speech. The docker image is about 2 GB big. It will print after a short period of not recognizing any speech input. Make sure your microphone doesn't pick up the text-to-speech output. See [Arguments](#arguments) for more information.

##### Arguments

Running without any argument uses the default PulseAudio source. To capture system audio set the `-d` option to the name of the "monitor of (built-in) audio analog stereo" source.

Optional arguments:

* -h, --help

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;print the help message and exit
* -l, --list_devices

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;show list of PulseAudio sources and exit (`pactl list short sources`)
* -d DEVICE, --device DEVICE

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;set PulseAudio source (index or name)
* --f, --filter

&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;use experimental noise suppression. Try this if you aren't satisfied with the result.


## TODO

* check buffer for ctrl + c in if loop of while true loop to quit
* improve conversion e.g. with grammar correction
* improve noise filtering
* make ffmpeg loglevel changeable as argument (an error is shown if the ALSA card doesn't exist even with log level quiet)
* is alsa-utils still required after changing to PulseAudio?
* make stream script quit properly during TTS
