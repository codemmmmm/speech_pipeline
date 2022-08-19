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

def print_green(str_to_color, str=""):
    ANSI_GREEN = "\u001b[32m"
    ANSI_RESET = "\u001b[0m"
    print(ANSI_GREEN + str_to_color + ANSI_RESET + str)

def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-l', '--list-devices', action='store_true',
        help='show list of ALSA sources and exit (\'pactl list short sources\')')
    parser.add_argument(
        '-d', '--device', default='default',
        help='set ALSA source (name (recommended) or index)')
    parser.add_argument(
        '-i', '--in-language', default="en", choices=("en", "de"),
        help='set input language')
    parser.add_argument(
        '-f', '--filter', action='store_true',
        help='use denoiser')
    return parser

def get_marian_names(lang) -> (str, str):
    #https://huggingface.co/Helsinki-NLP/opus-mt-en-de
    #https://huggingface.co/Helsinki-NLP/opus-mt-de-e
    marian_model_name_en = "Helsinki-NLP/opus-mt-en-de"
    marian_directory_en = 'marian-translate-en-de'
    marian_model_name_de = "Helsinki-NLP/opus-mt-de-en"
    marian_directory_de = 'marian-translate-de-en'
    if lang == "en":
        task = "translation_en_to_de"
        return (marian_model_name_en, marian_directory_en, task)
    else:
        task = "translation_de_to_en"
        return (marian_model_name_de, marian_directory_de, task)

def get_tts_name(in_lang) -> str:
    if in_lang == "en":
        # german speech output
        return "tts_models/de/thorsten/vits"
    else:
        # english speech output
        return "tts_models/en/vctk/vits"

def load_vosk_model(in_lang):
    """downloads model automatically"""
    vosk_model_name_en = "vosk-model-en-us-0.22"
    vosk_model_name_de = "vosk-model-de-0.21"
    try:
        if in_lang == "en":
            return Model(model_name=vosk_model_name_en)
        return Model(model_name=vosk_model_name_de)
    except Exception:
        sys.exit("Failed to find or download any Vosk model!")

def load_trans_models(marian_directory, marian_directory_en):
    if not os.path.exists(marian_directory):
        # download models and then load local model files
        trans_model = MarianMTModel.from_pretrained(marian_model_name)
        tokenizer = MarianTokenizer.from_pretrained(marian_model_name)
        tokenizer.save_pretrained(marian_directory)
        trans_model.save_pretrained(marian_directory)
    else:
        # load local model files
        trans_model = MarianMTModel.from_pretrained(marian_directory)
        tokenizer = MarianTokenizer.from_pretrained(marian_directory)
    return trans_model, tokenizer

def make_record_command(device: str, filter: bool, sample_rate):
    command = ('ffmpeg', '-loglevel', 'fatal', '-f', 'pulse', '-i', device,
            '-ar', str(sample_rate) , '-ac', '1', '-f', 's16le')
    # model for arnndn https://github.com/GregorR/rnnoise-models/tree/master/beguiling-drafter-2018-08-30
    noise_filter = ('-filter:a', 'afftdn=nf=-30') # 'afftdn=nf=-30,arnndn=m=beguiling-drafter-2018-08-30/bd.rnnn:mix=0.5'
    use_stdout = ('-',)
    return command + noise_filter + use_stdout if filter else command + use_stdout;

def synth(q, lock, translation, speaker_name):
    # lock to prevent tts-server returning a small sentence before a longer sentence that was requested earlier
    with lock:
        print("Calling TTS...")
        result = cTTS.synthesize(translation, speaker_name)
    if result:
        q.put(result)

def play(q, lock, play_command):
    play_process = subprocess.Popen(play_command, stdin=subprocess.PIPE)
    # lock to prevent playing multiple files at the same time
    with lock:
        play_process.communicate(q.get())

def main():
    if not sys.platform == "linux":
        sys.exit("Please use a linux OS.")
    # disable log prints
    SetLogLevel(-1)
    verbose = False

    args = get_argparser().parse_args()

    if args.list_devices:
        print("index   name")
        subprocess.run(['pactl', 'list', 'short', 'sources'])
        sys.exit()

    SAMPLE_RATE=16000
    # Initialise recognizer
    if verbose:
        print("Initialising recognizer...")
    rec_model = load_vosk_model(args.in_language)
    rec = KaldiRecognizer(rec_model, SAMPLE_RATE)

    # Initialise translator
    if verbose:
        print("Initialising translator...")
    marian_model_name, marian_directory, task = get_marian_names(args.in_language)
    trans_model, tokenizer = load_trans_models(marian_directory, marian_model_name)
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

    q = mp.Queue()
    synth_lock = mp.Lock()
    player_lock = mp.Lock()

    play_command = ('aplay', '-', '-t', 'wav')
    record_command = make_record_command(args.device, args.filter, SAMPLE_RATE)
    record_process = subprocess.Popen(record_command, stdout=subprocess.PIPE)
    if verbose:
        print("Starting recording...")    

    printed_silence = False # to prevent printing 'silence' too often    
    try:
        # check if subprocesses started successfully
        time.sleep(2) # without sleep it would check too early
        #if play_process.poll() not in (None, 0):
        #    raise Exception("aplay/ffplay player failed to start!")
        if record_process.poll() not in (None, 0): # should just be: if not None ?
            raise Exception("ffmpeg recorder failed to start!")

        print('#' * 80)
        print('Press Ctrl+C to stop recording')
        print('#' * 80)
        while True:
            # read ffmpeg stream
            recorded_audio = record_process.stdout.read(4000)
            if rec.AcceptWaveform(recorded_audio):
                result = json.loads(rec.Result())
                text = result['text']
                if text.strip() not in ("", "the"): # if text.trim() not in ("", "the", "one", "ln", "now", 'köln', 'einen' ...) or just discard all single word recognitions?
                    print_green(str_to_color="Recognized: ", str=text)
                    translation = translator(text)[0]['translation_text']
                    print_green(str_to_color="Translated: ", str=translation)
                    printed_silence = False                      
                    p_synth = mp.Process(target=synth, args=(q, synth_lock, translation, speaker_name if args.in_language == 'de' else None))
                    p_synth.start()
                    p_play = mp.Process(target=play, args=(q, player_lock, play_command))
                    p_play.start()
                else:
                    if not printed_silence:
                        print("* silence *\n")
                        printed_silence = True
    except KeyboardInterrupt:
        print('Done!')
    finally:
        #tts_server.kill()
        record_process.kill()

if __name__ == "__main__":
    main()