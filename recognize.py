from transformers import MarianMTModel, MarianTokenizer, pipeline 
from vosk import Model, KaldiRecognizer, SetLogLevel
import os
import sys
import json
import subprocess
import argparse
from transformers import MarianMTModel, MarianTokenizer, pipeline
import pyttsx3

SetLogLevel(-1)

if not sys.platform == "linux":
    sys.exit("Please use a linux OS.")

if not os.path.exists("model"):
    sys.exit("Please download the model from https://alphacephei.com/vosk/models and unpack as 'model' in the current folder.")

parser = argparse.ArgumentParser()
parser.add_argument(
    'file', help='file to recognize speech from')
parser.add_argument(
    '-f', '--filter', action='store_true',
    help='use experimental noise suppression')
args = parser.parse_args()

sample_rate=16000
model = Model("model")
rec = KaldiRecognizer(model, sample_rate)

#for arnndn https://github.com/GregorR/rnnoise-models/tree/master/beguiling-drafter-2018-08-30
command = ('ffmpeg', '-loglevel', 'quiet', '-i', args.file,
        '-ar', str(sample_rate) , '-ac', '1', '-f', 's16le')
noise_filter = ('-af', 'arnndn=m=beguiling-drafter-2018-08-30/bd.rnnn:mix=0.6')
stdout = ('-', ) #last part of the command

process = subprocess.Popen(command + noise_filter + stdout if args.filter else command + stdout, stdout=subprocess.PIPE)

print("Recognized:")
results = []
while True:
    data = process.stdout.read(4000)
    if len(data) == 0:
        break
    if rec.AcceptWaveform(data):
        res = json.loads(rec.Result())
        sequence = res['text']
        #add a if sequence != "":
        print(sequence)
        results.append(sequence)

res = json.loads(rec.FinalResult())
results.append(res['text'])
print(res['text'])

translations = []
print("\nTranslated:")
directory = 'translate-en-de'
tokenizer = MarianTokenizer.from_pretrained(directory)
model = MarianMTModel.from_pretrained(directory)
translator = pipeline("translation_en_to_de", model=model, tokenizer=tokenizer)
for string in translator(results):
    translation = string['translation_text']
    translations.append(translation)
    print(translation)

engine = pyttsx3.init()
engine.setProperty('rate', 180)
engine.setProperty('voice', 'german' + '+f2') #or '+m2'
print("\nTalking...")
for string in translations:
    engine.say(string)
engine.runAndWait()