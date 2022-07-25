from transformers import MarianMTModel, MarianTokenizer, pipeline 
from vosk import Model, KaldiRecognizer, SetLogLevel
import os
import sys
import json
import subprocess
import argparse
# pylint: disable=redefined-outer-name, unused-argument
from pathlib import Path

from TTS.utils.manage import ModelManager
from TTS.utils.synthesizer import Synthesizer

def get_marian_names(lang) -> (str, str):
    #https://huggingface.co/Helsinki-NLP/opus-mt-en-de
    #https://huggingface.co/Helsinki-NLP/opus-mt-de-e
    marian_model_name_en = "Helsinki-NLP/opus-mt-en-de"
    marian_directory_en = 'marian-translate-en-de'
    marian_model_name_de = "Helsinki-NLP/opus-mt-de-en"
    marian_directory_de = 'marian-translate-de-en'
    if lang == "en":
        return (marian_model_name_en, marian_directory_en, "translation_en_to_de")
    else:
        return (marian_model_name_de, marian_directory_de, "translation_de_to_en")

def get_tts_name(lang) -> str:
    if lang == "en":
        # german speech output
        return "tts_models/de/thorsten/vits"
    else:
        # english speech output
        return "tts_models/en/vctk/vits" # "--speaker_idx", "p227"

def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-l', '--list-devices', action='store_true',
        help='show list of PulseAudio sources and exit (\'pactl list short sources\')')
    parser.add_argument(
        '-d', '--device', default='default',
        help='set PulseAudio source (index or name)')
    parser.add_argument(
        '-i', '--in-language', default="en", choices=("en", "de"),
        help='set input language')
    parser.add_argument(
        '-f', '--filter', action='store_true',
        help='use experimental noise suppression')
    return parser

if not sys.platform == "linux":
    sys.exit("Please use a linux OS.")
SetLogLevel(-1)
verbose = False

args = get_argparser().parse_args()

if args.list_devices:
    print("index   name")
    subprocess.run(['pactl', 'list', 'short', 'sources'])
    sys.exit(0)

tts_model_name = get_tts_name(args.in_language)

# Code taken and maybe adjusted from TTS/bin/synthesize.py
# load model manager
#path = Path(__file__).parent / "../.models.json"
path = "/home/moritz/python/TTS/TTS/.models.json"
manager = ModelManager(path)

model_path = None
config_path = None
speakers_file_path = None
language_ids_file_path = None
vocoder_path = None
vocoder_config_path = None
encoder_path = None
encoder_config_path = None

# load pre-trained model paths
model_path, config_path, model_item = manager.download_model(tts_model_name)
vocoder_name = model_item["default_vocoder"]

# load models
synthesizer = Synthesizer(
    model_path,
    config_path,
    speakers_file_path,
    language_ids_file_path,
    vocoder_path,
    vocoder_config_path,
    encoder_path,
    encoder_config_path,
)

# kick it
wav = synthesizer.tts(
    "Good morning.", # text
    "p227", # speaker_idx
)

# save the results
out_path = "speech.wav"
print(" > Saving output to {}".format(out_path))
synthesizer.save_wav(wav, out_path)


sys.exit()


sample_rate=16000
# Initialise recognizer
if verbose:
    print("Initialising recognizer...")
vosk_model_name_en = "vosk-model-en-us-0.22"
vosk_model_name_de = "vosk-model-de-0.21"
try:
    if args.in_language == "en":
        rec_model = Model(model_name=vosk_model_name_en)
    else:
        rec_model = Model(model_name=vosk_model_name_de)
except Exception:
    sys.exit("Failed to download any Vosk model!")
rec = KaldiRecognizer(rec_model, sample_rate)

# make recording command
#for arnndn https://github.com/GregorR/rnnoise-models/tree/master/beguiling-drafter-2018-08-30
#command = ('ffmpeg', '-loglevel', 'quiet', '-f', 'alsa', '-i', args.device,
#        '-ar', str(sample_rate) , '-ac', '1', '-f', 's16le') #without pavucontrol
command = ('ffmpeg', '-loglevel', 'quiet', '-f', 'pulse', '-i', args.device,
        '-ar', str(sample_rate) , '-ac', '1', '-f', 's16le')
noise_filter = ('-af', 'arnndn=m=beguiling-drafter-2018-08-30/bd.rnnn:mix=0.6')
stdout = ('-', ) #last part of the command

# Initialise translator
if verbose:
    print("Initialising translator...")
marian_model_name, marian_directory, task = get_marian_names(args.in_language)
if not os.path.exists(marian_directory):
    trans_model = MarianMTModel.from_pretrained(marian_model_name)
    tokenizer = MarianTokenizer.from_pretrained(marian_model_name)
    tokenizer.save_pretrained(marian_directory)
    trans_model.save_pretrained(marian_directory)
else:
    trans_model = MarianMTModel.from_pretrained(marian_directory)
    tokenizer = MarianTokenizer.from_pretrained(marian_directory)
translator = pipeline(task=task, model=trans_model, tokenizer=tokenizer)

if verbose:
    print("Starting recording...")
process = subprocess.Popen(command + noise_filter + stdout if args.filter else command + stdout, stdout=subprocess.PIPE)
print('#' * 80)
print('Press Ctrl+C to stop recording')
print('#' * 80)
try:
    printed_silence = False
    while True:
        # read mic data
        data = process.stdout.read(4000)
        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            sequence = res['text']
            if sequence != "": #why does it detect empty lines sometimes?
                print("Recognized: " + sequence)

                translation = translator(sequence)[0]['translation_text'] #structure: [{'translation_text': 'Guten Morgen.'}]
                print("Translated: " + translation)
                printed_silence = False

                speech_file = "speech.wav"                
                subprocess.run(["tts", "--out_path", speech_file, "--text", translation, "--model_name", tts_model_name])             
                print("Saved synthesized speech to file speech.wav..."  + "\n")   
                print("Playing file...")
                subprocess.run(["ffplay", speech_file, "-autoexit", "-loglevel", "error"])
                
            else:
                if not printed_silence:
                    print("* silence *\n")
                    printed_silence = True

except KeyboardInterrupt:
    print('Done!')    

#final result doesn't do anything?
#res = json.loads(rec.FinalResult())