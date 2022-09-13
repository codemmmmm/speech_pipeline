from transformers import MarianMTModel, MarianTokenizer, pipeline 
from vosk import Model, KaldiRecognizer, SetLogLevel
import os
import sys
import json
import subprocess
from subprocess import CalledProcessError
import argparse
import time
import multiprocessing as mp
import logging

import cTTS # my own edited and not from package

def print_green(str_to_color, str=""):
    ansi_green = "\u001b[32m"
    ansi_reset = "\u001b[0m"
    print(ansi_green + str_to_color + ansi_reset + str)

def get_argparser():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-i', '--in-language', default="en", choices=("en", "de"),
        help='set input language')
    parser.add_argument(
        '-f', '--filter', action='store_true',
        help='use noise filter')

    subparsers = parser.add_subparsers(required=True, dest='subcommand')
    parser_mic = subparsers.add_parser('mic')
    parser_mic.add_argument(
        '-l', '--list-devices', action='store_true',
        help='show list of ALSA sources and exit (\'pactl list short sources\')')
    parser_mic.add_argument(
        '-d', '--device', default='default',
        help='set ALSA source (name (recommended) or index)')

    parser_video = subparsers.add_parser('video')
    parser_video.add_argument(
            'in_video',
            help='video file for input')
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
    except Exception as e:
        sys.exit("Exception: " + str(e))

def load_trans_models(marian_directory, marian_model_name):
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

def get_sample_rate(file_path):
    """Get sample rate of audio channel 0"""
    try:
        return int(subprocess.run(('ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=sample_rate', '-of', 'default=noprint_wrappers=1:nokey=1', file_path),
            check=True, stdout=subprocess.PIPE).stdout)
    except CalledProcessError as e:
        sys.exit(e)

def make_ffmpeg_command_mic(device: str, filter: bool, sample_rate: int):
    command = ('ffmpeg', '-loglevel', 'fatal', '-f', 'pulse', '-i', device,
            '-ar', str(sample_rate) , '-ac', '1', '-f', 's16le')
    # model for arnndn https://github.com/GregorR/rnnoise-models/tree/master/beguiling-drafter-2018-08-30
    noise_filter = ('-filter:a', 'afftdn=nf=-30') # 'afftdn=nf=-30,arnndn=m=beguiling-drafter-2018-08-30/bd.rnnn:mix=0.5'
    use_stdout = ('-',)
    return command + noise_filter + use_stdout if filter else command + use_stdout

def make_ffmpeg_command_video(in_video: str, video_pipe_name: str, filter: bool) -> str:
    # read video file, write to pipe for player, convert to single channel audio and write to stdout for recognizer
    command = ('ffmpeg', '-y', '-loglevel', 'fatal', '-i', in_video,
            '-movflags', 'empty_moov', '-codec', 'copy', '-f', 'mp4', video_pipe_name,
            '-ac', '1', '-f', 'wav',)
    # model for arnndn https://github.com/GregorR/rnnoise-models/tree/master/beguiling-drafter-2018-08-30
    noise_filter = ('-filter:a', 'afftdn=nf=-30') # 'afftdn=nf=-30,arnndn=m=beguiling-drafter-2018-08-30/bd.rnnn:mix=0.5'
    use_stdout = ('-',)
    return command + noise_filter + use_stdout if filter else command + use_stdout

def get_text_from_result(result):
    return json.loads(result)['text']

def synth(tts_audio_queue, lock, translation, speaker_name):
    # lock to prevent tts-server returning a small sentence before a longer sentence that was requested earlier
    with lock:
        logging.info("Calling TTS...")
        result = cTTS.synthesize(translation, speaker_name)
    if result:
        tts_audio_queue.put(result)

def play(tts_audio_queue, lock, play_tts_command):
    play_process = subprocess.Popen(play_tts_command, stdin=subprocess.PIPE)
    # lock to prevent playing multiple files at the same time
    with lock:
        play_process.communicate(tts_audio_queue.get())

def translate_synthesize_play(text, translator, tts_audio_queue, synth_lock, player_lock, speaker_name, play_tts_command):
    print_green(str_to_color="Recognized: ", str=text)
    translation = translator(text)[0]['translation_text']
    print_green(str_to_color="Translated: ", str=translation + "\n")
    p_synth = mp.Process(target=synth, args=(tts_audio_queue, synth_lock, translation, speaker_name))
    p_synth.start()
    p_play = mp.Process(target=play, args=(tts_audio_queue, player_lock, play_tts_command))
    p_play.start()

def main_loop_mic(ffmpeg_process, recognizer, translator, tts_audio_queue, synth_lock, player_lock, speaker_name, play_tts_command):
    # to prevent printing 'silence' too often
    printed_silence = False
    while True:
        # read ffmpeg stream
        audio = ffmpeg_process.stdout.read(4000)
        if recognizer.AcceptWaveform(audio):
            text = get_text_from_result(recognizer.Result())
            if text.strip() not in ("", "the"): # if text.trim() not in ("", "the", "one", "ln", "now", 'köln', 'einen' ...) or just discard all single word recognitions?
                translate_synthesize_play(text, translator, tts_audio_queue, synth_lock, player_lock, speaker_name, play_tts_command)
                printed_silence = False
            else:
                if not printed_silence:
                    print("* silence *\n")
                    printed_silence = True

def main_loop_video(ffmpeg_process, recognizer, translator, tts_audio_queue, synth_lock, player_lock, speaker_name, play_tts_command):
    file_exhausted = False
    while not file_exhausted:
        text = ""
        # read ffmpeg stream
        audio = ffmpeg_process.stdout.read(4000)
        if recognizer.AcceptWaveform(audio):
            text = get_text_from_result(recognizer.Result())
        elif len(audio) == 0:
            # process last words after file is exhausted (recognizer.AcceptWaveform will not return True)
            text = get_text_from_result(recognizer.FinalResult())
            file_exhausted = True
        if text.strip() not in ("", "the"): # if text.strip() not in ("", "the", "one", "ln", "now", 'köln', 'einen' ...) or just discard all single word recognitions?
            translate_synthesize_play(text, translator, tts_audio_queue, synth_lock, player_lock, speaker_name, play_tts_command)

def main():
    if not sys.platform == "linux":
        sys.exit("Please use a linux OS.")
    # disable vosk log prints
    SetLogLevel(-1)
    logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.WARNING)

    args = get_argparser().parse_args()
    if args.subcommand == "mic":
        print("Setting up recognizer on microphone stream...")
    else:
        print("Setting up recognizer on video file...")
    
    if args.subcommand == "mic":
        if args.list_devices:
            print("index   name")
            subprocess.run(['pactl', 'list', 'short', 'sources'])
            sys.exit()

    if args.subcommand == "mic":
        # maybe a higher value would be useful, vosk example shows it with 16000
        sample_rate=16000
    else:
        logging.info("Getting audio channel's sample rate")
        sample_rate = get_sample_rate(args.in_video)
    # Initialise recognizer
    logging.info("Initialising recognizer...")
    rec_model = load_vosk_model(args.in_language)
    recognizer = KaldiRecognizer(rec_model, sample_rate)

    # Initialise translator
    logging.info("Initialising translator...")
    marian_model_name, marian_directory, task = get_marian_names(args.in_language)
    trans_model, tokenizer = load_trans_models(marian_directory, marian_model_name)
    translator = pipeline(task=task, model=trans_model, tokenizer=tokenizer)

    # Initialise TTS
    logging.info("Starting tts-server...")
    tts_model_name = get_tts_name(args.in_language)
    tts_server_process = subprocess.Popen(["tts-server", "--model_name", tts_model_name], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    # wait till tts-server finished loading
    logging.info("Waiting for tts-server to be available")
    curl_cmd = ['curl', 'localhost:5002', '--silent', '--output', '/dev/null']
    curl = subprocess.run(curl_cmd)
    while curl.returncode != 0:
        time.sleep(0.5)
        curl = subprocess.run(curl_cmd)
    speaker_name = 'p364' if args.in_language == 'de' else None # "--speaker_idx", "p227" "p364" "ED\n"

    # pipe for playing the video
    video_pipe_name = 'video_pipe'
    if os.path.exists(video_pipe_name):
        os.remove(video_pipe_name)
    os.mkfifo(video_pipe_name)  

    tts_audio_queue = mp.Queue()
    synth_lock = mp.Lock()
    player_lock = mp.Lock()

    play_tts_command = ('aplay', '-', '-t', 'wav', '--quiet')
    if args.subcommand == "mic":
        ffmpeg_command = make_ffmpeg_command_mic(args.device, args.filter, sample_rate)
    else:
        ffmpeg_command = make_ffmpeg_command_video(args.in_video, video_pipe_name, args.filter)
    logging.info("Starting ffmpeg...")
    ffmpeg_process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE)
    if args.subcommand == "video":
        logging.info('Starting mpv...')
        subprocess.Popen(('mpv', video_pipe_name, '--really-quiet', '--volume=32'))

    try:
        # check if subprocesses started successfully
        time.sleep(2) # without sleep it would check too early
        if ffmpeg_process.poll() not in (None, 0): # should just be: if not None ?
            raise Exception("ffmpeg failed to start!")

        print('#' * 80)
        print('Press Ctrl+C to stop')
        print('#' * 80)
        if args.subcommand == "mic":
            main_loop_mic(ffmpeg_process, recognizer, translator, tts_audio_queue, synth_lock, player_lock, speaker_name, play_tts_command)
        else:
            main_loop_video(ffmpeg_process, recognizer, translator, tts_audio_queue, synth_lock, player_lock, speaker_name, play_tts_command)
    except KeyboardInterrupt:
        print_green('Done!')
    finally:
        tts_server_process.kill()
        ffmpeg_process.kill()
        if args.subcommand == "video":
            os.remove(video_pipe_name)

if __name__ == "__main__":
    main()