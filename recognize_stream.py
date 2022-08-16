from transformers import MarianMTModel, MarianTokenizer, pipeline 
from vosk import Model, KaldiRecognizer, SetLogLevel
import os
import sys
import json
import subprocess
import argparse
import time
import multiprocessing as mp

import cTTS # my own edited and not from package

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
        return "tts_models/en/vctk/vits"

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

def synth(q, translation, speaker_name):
    print("Synthesizing speech...(calling)")
    q.put(cTTS.synthesize(translation, speaker_name))

def play(q, play_command, lock):
    play_process = subprocess.Popen(play_command, stdin=subprocess.PIPE)
    #with lock:
    play_process.communicate(q.get())

if not sys.platform == "linux":
    sys.exit("Please use a linux OS.")
SetLogLevel(-1)
verbose = False

args = get_argparser().parse_args()

if args.list_devices:
    print("index   name")
    subprocess.run(['pactl', 'list', 'short', 'sources'])
    sys.exit(0)

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
#command = ('ffmpeg', '-loglevel', 'fatal', '-f', 'alsa', '-i', args.device,
#        '-ar', str(sample_rate) , '-ac', '1', '-f', 's16le') #without PulseAudio
record_command = ('ffmpeg', '-loglevel', 'fatal', '-f', 'pulse', '-i', args.device,
        '-ar', str(sample_rate) , '-ac', '1', '-f', 's16le')
noise_filter = ('-af', 'arnndn=m=beguiling-drafter-2018-08-30/bd.rnnn:mix=0.6')
stdout = ('-',) #last part of the command
# make play command
play_command = ('aplay', '-', '-t', 'wav')

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

# # Initialise TTS
# if verbose:
#     print("Starting tts-server...")
# tts_model_name = get_tts_name(args.in_language)
# tts_server = subprocess.Popen(["tts-server", "--model_name", tts_model_name])
# # wait till tts-server finished loading
# curl_cmd = ['curl', 'localhost:5002', '--silent', '--output', '/dev/null']
# curl = subprocess.run(curl_cmd)
# while curl.returncode != 0:
#     time.sleep(0.5)
#     curl = subprocess.run(curl_cmd)
speaker_name = 'p364' # "--speaker_idx", "p227" "p364" "ED\n"

if verbose:
    print("Starting recording...")
record_process = subprocess.Popen(record_command + noise_filter + stdout if args.filter else record_command + stdout, stdout=subprocess.PIPE)
#play_process = subprocess.Popen(['ffplay', 'pipe:0', '-nodisp', '-autoexit'], stdin=subprocess.PIPE) # -f wav "-loglevel", "error"
#play_process = subprocess.Popen(['ffplay', '-', '-nodisp', '-f', 'wav'], stdin=tts_pipe_read) # -f qwav "-loglevel", "error"
#play_process = subprocess.Popen(['ffplay', pipe_name, '-nodisp', '-f', 'wav']) # -f wav "-loglevel", "error"
#play_process = subprocess.Popen(['aplay', pipe_name, '-t', 'wav', '--buffer-time', '1000000', '--buffer-size', '8192', '--period-size', '10000', '-N']) # -N , '--buffer-time', '10000', '--buffer-size', '8192'
#play_process = subprocess.Popen(['aplay', '-', '-t', 'wav'], stdin=subprocess.PIPE) # -N

q = mp.Queue()
lock = mp.Lock()
printed_silence = False # to prevent printing 'silence' too often
ansi_green = "\u001b[32m"
ansi_reset = "\u001b[0m"
try:
    # check if subprocesses started successfully
    time.sleep(2) # without sleep it would check too early
    #if play_process.poll() not in (None, 0):
    #    raise Exception("aplay/ffplay player failed to start!")
    if record_process.poll() not in (None, 0):
        raise Exception("ffmpeg recorder failed to start!")

    print('#' * 80)
    print('Press Ctrl+C to stop recording')
    print('#' * 80)
    while True:
        # read ffmpeg stream
        recorded_audio = record_process.stdout.read(4000)
        if rec.AcceptWaveform(recorded_audio):
            res = json.loads(rec.Result()) #final result doesn't do anything?
            sequence = res['text']
            if sequence != "":
                print(ansi_green + "Recognized: "+ ansi_reset + sequence)

                translation = translator(sequence)[0]['translation_text']
                print(ansi_green + "Translated: "+ ansi_reset + translation)
                printed_silence = False                      
                # does the synth need to be called as a process?
                p_write = mp.Process(target=synth, args=(q, translation, speaker_name if args.in_language == 'de' else None))
                p_write.start()
                p_read = mp.Process(target=play, args=(q, play_command, lock))
                p_read.start()
            else:
                if not printed_silence:
                    print("* silence *\n")
                    printed_silence = True
except KeyboardInterrupt:
    print('Done!')
finally:
    #tts_server.kill()
    record_process.kill()
    #play_process.kill()