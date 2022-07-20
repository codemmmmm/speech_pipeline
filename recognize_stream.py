from transformers import MarianMTModel, MarianTokenizer, pipeline 
from vosk import Model, KaldiRecognizer, SetLogLevel
import os
import sys
import json
import subprocess
import argparse
from transformers import MarianMTModel, MarianTokenizer, pipeline

SetLogLevel(-1)

verbose = False

if not sys.platform == "linux":
    sys.exit("Please use a linux OS.")

parser = argparse.ArgumentParser()
parser.add_argument(
    '-l', '--list-devices', action='store_true',
    help='show list of PulseAudio sources and exit (\'pactl list short sources\')')
parser.add_argument(
    '-d', '--device', default='default',
    help='set PulseAudio source (index or name)')
parser.add_argument(
    '-i', '--in-language', default="en", choices=("en", "de"),
    help='set input language (en or de)')
parser.add_argument(
    '-f', '--filter', action='store_true',
    help='use experimental noise suppression')
args = parser.parse_args()

if args.list_devices:
    print("index   name")
    subprocess.run(['pactl', 'list', 'short', 'sources'])
    sys.exit(0)

lang = "en"

sample_rate=16000
# Initialise recognizer
if verbose:
    print("Initialising recognizer...")
vosk_model_name_en = "vosk-model-en-us-0.22"
vosk_model_name_de = "vosk-model-de-0.21"
try:
    if lang == "en":
        model = Model(model_name=vosk_model_name_en)
    else:
        model = Model(model_name=vosk_model_name_de)
except Exception:
    sys.exit("No model could be downloaded!")
rec = KaldiRecognizer(model, sample_rate)

#for arnndn https://github.com/GregorR/rnnoise-models/tree/master/beguiling-drafter-2018-08-30
#command = ('ffmpeg', '-loglevel', 'quiet', '-f', 'alsa', '-i', args.device,
#        '-ar', str(sample_rate) , '-ac', '1', '-f', 's16le') #without pavucontrol
command = ('ffmpeg', '-loglevel', 'quiet', '-f', 'pulse', '-i', args.device,
        '-ar', str(sample_rate) , '-ac', '1', '-f', 's16le')
noise_filter = ('-af', 'arnndn=m=beguiling-drafter-2018-08-30/bd.rnnn:mix=0.6')
stdout = ('-', ) #last part of the command

#Initialise translator
if verbose:
    print("Initialising translator...")
directory = 'translate-en-de'
tokenizer = MarianTokenizer.from_pretrained(directory)
model = MarianMTModel.from_pretrained(directory)
translator = pipeline("translation_en_to_de", model=model, tokenizer=tokenizer)

try:
    if verbose:
        print("Starting recording...")
    process = subprocess.Popen(command + noise_filter + stdout if args.filter else command + stdout, stdout=subprocess.PIPE)
    print('#' * 80)
    print('Press Ctrl+C to stop recording')
    print('#' * 80)
 
    printed_silence = False
    while True:
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
                print("Saving synthesized speech to file speech.wav..."  + "\n")   
                subprocess.run(["tts", "--out_path", speech_file, "--text", translation, "--model_name", "tts_models/de/thorsten/vits"])             
                print("Playing file...")
                subprocess.run(["ffplay", speech_file, "-autoexit", "-loglevel", "error"])
                print("Deleting file...")
                os.remove(speech_file)
                
            else:
                if not printed_silence:
                    print("* silence *\n")
                    printed_silence = True

except KeyboardInterrupt:
    print('Done!')    

#final result doesn't do anything?
#res = json.loads(rec.FinalResult())