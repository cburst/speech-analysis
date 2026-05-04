#!/usr/bin/env python
# coding: utf-8
"""
Combined Script:
Part 1 – CSV Processing & Audio Download:
  - Changes to a hardcoded base directory.
  - Authenticates with Google Drive.
  - Creates a folder (named after the CSV file without extension) and writes text files.
  - Downloads two audio files and processes the student audio to produce studentaudio_adjusted_cleaned.wav.
Part 2 – Pronunciation Assessment:
  - Reads the transcript (text.txt) and splits it into sentences.
  - Uses Azure Speech SDK to obtain word-level timestamps from studentaudio_adjusted_cleaned.wav.
  - Aligns recognized words with the transcript to determine sentence boundaries.
  - Segments the audio into individual sentence files saved in a “segments” subfolder.
  - Runs pronunciation assessment on each segmented sentence file and writes results to two CSV files.
"""

import os
import csv
import sys
import re
import io
import pickle
import subprocess
import shutil
import time
import json
import nltk
import string
import difflib
from tqdm import tqdm
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import azure.cognitiveservices.speech as speechsdk

# Declare global variable for recognition control
done = False

# ------------------------------------------------------------------
# strip out / normalize “funny” quotation marks and other stray chars
def sanitize_text_field(s: str) -> str:
    # turn line‐breaks into spaces so tokenization doesn't break
    s = s.replace('\r', ' ').replace('\n', ' ')
    replacements = {
        '“': "'", '”': "'",  # curly double quotes
        '‘': "'", '’': "'",  # curly single quotes
        '~': "'",            # tilde
        '→': "'", '←': "'",  # arrows
        '—': '-', '–': '-',  # em/en dashes → hyphen
        '…': '...',          # ellipsis
        # add any others you find here:
        # '\u00A0': ' ',      # non-breaking space → normal space
    }
    return s.translate(str.maketrans(replacements))

# ------------------------------------------------------------------

def send_error_email_applescript(error_message):
    # AppleScript to send an email via the Mail app.
    # Customize the recipient email address as needed.
    applescript_cmd = f'''
    tell application "Mail"
        set newMessage to make new outgoing message with properties {{subject:"Speech API Communication Error", content:"{error_message}", visible:false}}
        tell newMessage
            make new to recipient at end of to recipients with properties {{address:"cburst@gmail.com"}}
            send
        end tell
    end tell
    '''
    try:
        subprocess.run(["osascript", "-e", applescript_cmd], check=True)
        print("Error email sent via AppleScript.")
    except Exception as e:
        print(f"Failed to send error email: {e}")

# ------------------- Part 1: CSV Processing & Audio Download -------------------

# Google API Scope and credentials
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
TOKEN_FILE = "token.pickle"
CREDENTIALS_FILE = "client_secret.json"

# Hardcoded working directory (all CSV-related folders will be created here)
BASE_DIR = os.path.expanduser("~/DropboxM/efficient student management resources")
os.chdir(BASE_DIR)
print(f"📁 Changed working directory to {os.getcwd()}")

DESIRED_VOLUME_THRESHOLD = -20.0  # in dB

def authenticate_google_api():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    return creds

def extract_drive_file_id(url):
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    match_alt = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match_alt:
        return match_alt.group(1)
    print(f"⚠️ Could not extract file ID from URL: {url}")
    return None

def analyze_volume(file_path):
    print(f"🎚️ Analyzing volume for {file_path}")
    cmd = ['ffmpeg', '-i', file_path, '-filter:a', 'volumedetect', '-f', 'null', 'NUL' if os.name == 'nt' else '/dev/null']
    result = subprocess.run(cmd, text=True, stderr=subprocess.PIPE)
    mean_volume = re.search(r"mean_volume: ([-\d.]+) dB", result.stderr)
    if mean_volume:
        print(f"📊 Mean Volume: {mean_volume.group(1)} dB")
    else:
        print(f"⚠️ Could not analyze volume for {file_path}")
    return float(mean_volume.group(1)) if mean_volume else None

def adjust_volume(file_path, destination_folder):
    mean_volume = analyze_volume(file_path)
    if mean_volume is None:
        return file_path  # analysis failed; return original
    required_increase = DESIRED_VOLUME_THRESHOLD - mean_volume
    file_root = os.path.splitext(os.path.basename(file_path))[0]
    # Create an adjusted file name e.g. studentaudio_adjusted.wav
    wav_file = os.path.join(destination_folder, f"{file_root}_adjusted.wav")
    if required_increase > 0:
        print(f"🎚️ Increasing volume by {required_increase} dB and converting {file_path} to WAV")
        subprocess.run(['ffmpeg', '-i', file_path, '-filter:a', f'volume={required_increase}dB', wav_file], check=True)
    else:
        print(f"✔ Volume is above threshold. Converting {file_path} to WAV")
        subprocess.run(['ffmpeg', '-i', file_path, wav_file], check=True)
    return wav_file

def apply_noise_filter(input_file, destination_folder):
    # Ensure the adjusted tag is preserved so that we get studentaudio_adjusted_cleaned.wav
    file_root, _ = os.path.splitext(os.path.basename(input_file))
    if not file_root.endswith("_adjusted"):
        file_root = file_root + "_adjusted"
    cleaned_file = os.path.join(destination_folder, f"{file_root}_cleaned.wav")
    print(f"🧹 Applying noise filter to {input_file}")
    subprocess.run(['ffmpeg', '-i', input_file, '-af', 'afftdn', cleaned_file], check=True)
    # Optionally remove the intermediate adjusted file if desired
    if os.path.exists(input_file):
        os.remove(input_file)
        print(f"🗑️ Removed temporary file: {input_file}")
    print(f"✅ Noise-filtered audio saved as {cleaned_file}")
    return cleaned_file

def convert_to_wav(file_path, destination_folder):
    file_root = os.path.splitext(os.path.basename(file_path))[0]
    wav_file = os.path.join(destination_folder, f"{file_root}.wav")
    print(f"🔄 Converting {file_path} to WAV")
    subprocess.run(['ffmpeg', '-i', file_path, wav_file], check=True)
    return wav_file

def download_from_google_drive(file_id, destination_folder, target_filename, service, process_audio=False, convert_only=False):
    try:
        request = service.files().get_media(fileId=file_id)
        file_metadata = service.files().get(fileId=file_id).execute()
        original_filename = file_metadata.get('name', 'downloaded_file')
        file_extension = os.path.splitext(original_filename)[1]
        target_filename_with_ext = f"{target_filename}{file_extension}"
        file_path = os.path.join(destination_folder, target_filename_with_ext)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done_download = False
        pbar = tqdm(total=100, desc=f"📥 Downloading {target_filename_with_ext}", unit='%')
        while not done_download:
            status, done_download = downloader.next_chunk()
            pbar.update(int(status.progress() * 100) - pbar.n)
        pbar.close()
        with open(file_path, 'wb') as f:
            f.write(fh.getvalue())
        print(f"✅ Downloaded: {file_path}")
        if process_audio:
            volume_adjusted_file = adjust_volume(file_path, destination_folder)
            cleaned_file = apply_noise_filter(volume_adjusted_file, destination_folder)
            return cleaned_file
        elif convert_only:
            return convert_to_wav(file_path, destination_folder)
        else:
            return file_path
    except Exception as e:
        print(f"❌ Error downloading file from Google Drive: {e}")
        return None

def create_text_file(folder, filename, content):
    file_path = os.path.join(folder, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Created {filename}")

def process_csv(csv_filename):
    creds = authenticate_google_api()
    service = build('drive', 'v3', credentials=creds)
    if not os.path.isfile(csv_filename):
        print(f"❌ Error: File '{csv_filename}' not found.")
        return
    with open(csv_filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile, quoting=csv.QUOTE_MINIMAL)
        row = next(reader)
    student_number     = row[3]
    student_audio_link = row[5]
    raw_text           = row[4]
    text               = sanitize_text_field(raw_text)
    email              = row[1]
    name               = row[2]
    folder_name        = os.path.splitext(csv_filename)[0]
    os.makedirs(folder_name, exist_ok=True)
    create_text_file(folder_name, "name.txt", name)
    create_text_file(folder_name, "studentnumber.txt", student_number)
    create_text_file(folder_name, "text.txt", text)
    create_text_file(folder_name, "email.txt", email)
    # Process Student Audio (download, adjust volume, noise filter)
    if student_audio_link:
        student_audio_id = extract_drive_file_id(student_audio_link)
        if student_audio_id:
            download_from_google_drive(student_audio_id, folder_name, "studentaudio", service, process_audio=True)
    # Download Model Audio (convert to WAV only)
    # if model_audio_link:
    #     model_audio_id = extract_drive_file_id(model_audio_link)
    #     if model_audio_id:
    #         download_from_google_drive(model_audio_id, folder_name, "modelaudio", service, convert_only=True)

# ------------------- Part 2: Pronunciation Assessment -------------------

# Azure Speech Service configuration
speech_key     = "YOUR API KEY HERE"
service_region = "REGION HERE"
language       = "en-US"

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("⚠️ Usage: python combined_script.py <csv_filename>")
        sys.exit(1)

    # Part 1: Process CSV and download/process audio
    csv_filename = sys.argv[1]
    process_csv(csv_filename)
    folder_name = os.path.splitext(csv_filename)[0]

    # Define paths for transcript and processed student audio
    transcript_filename = os.path.join(folder_name, "text.txt")
    full_audio_filename = os.path.join(folder_name, "studentaudio_adjusted_cleaned.wav")
    if not os.path.exists(full_audio_filename):
        print(f"❌ Processed student audio not found: {full_audio_filename}")
        sys.exit(1)
    if not os.path.exists(transcript_filename):
        print(f"❌ Transcript file not found: {transcript_filename}")
        sys.exit(1)

    print("\nStarting pronunciation assessment...")
    print(f"Audio: {full_audio_filename}")
    print(f"Transcript: {transcript_filename}\n")

    # Prepare output CSV file paths (saved inside the CSV folder)
    sentence_csv_file = os.path.join(folder_name, "sentence_level_results.csv")
    word_csv_file     = os.path.join(folder_name, "word_level_results.csv")

    # Create a subfolder for segmented sentence audio files
    segments_folder = os.path.join(folder_name, "segments")
    os.makedirs(segments_folder, exist_ok=True)

    # Step 1: Read and sentence-segment the transcript
    with open(transcript_filename, "r", encoding="utf-8") as f:
        transcript = f.read().strip()
    # Ensure NLTK sentence tokenizer is ready (uncomment if needed)
    # nltk.download('punkt')
    sentences = nltk.sent_tokenize(transcript)

    def normalize_text(t):
        return [w.strip(string.punctuation).lower() for w in t.split() if w.strip(string.punctuation)]
    ref_words = normalize_text(transcript)

    # Step 2: Use Azure Speech SDK to get word-level timestamps for full audio
    try:
        speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
        speech_config.output_format = speechsdk.OutputFormat.Detailed
        speech_config.request_word_level_timestamps()
        speech_config.set_property(speechsdk.PropertyId.SpeechServiceResponse_PostProcessingOption, "TrueText")
        audio_config = speechsdk.audio.AudioConfig(filename=full_audio_filename)
        speech_recognizer = speechsdk.SpeechRecognizer(
            speech_config=speech_config,
            language=language,
            audio_config=audio_config
        )
    except Exception as api_error:
        error_message = f"Error during Azure Speech API initialization: {str(api_error)}"
        print(error_message)
        send_error_email_applescript(error_message)
        sys.exit(1)

    # Global variables for recognition callbacks are already defined (done, recognized_words)
    recognized_words = []

    def stop_cb(evt: speechsdk.SessionEventArgs):
        global done
        done = True

    def recognized_cb(evt: speechsdk.SpeechRecognitionEventArgs):
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            result_json = json.loads(evt.result.json)
            words = result_json["NBest"][0]["Words"]
            recognized_words.extend(words)
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            print("No speech recognized for a segment.")

    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)

    # Reset the global flag before recognition
    done = False
    speech_recognizer.start_continuous_recognition()
    while not done:
        time.sleep(0.5)
    speech_recognizer.stop_continuous_recognition()

    # Convert HNS (100-nanosecond units) to seconds for each recognized word
    for w in recognized_words:
        w['StartTimeSec'] = w['Offset'] / 10_000_000.0
        w['EndTimeSec']   = (w['Offset'] + w['Duration']) / 10_000_000.0
    hyp_words = [w['Word'].lower() for w in recognized_words]

    # Step 3: Align recognized words to transcript words
    s = difflib.SequenceMatcher(None, ref_words, hyp_words)
    ops = s.get_opcodes()
    ref_to_hyp_map = {}
    for tag, i1, i2, j1, j2 in ops:
        if tag in ('equal', 'replace'):
            for ri, hi in zip(range(i1, i2), range(j1, j2)):
                ref_to_hyp_map[ri] = hi

    # Step 4: Determine sentence boundaries using word alignment
    sentence_segments = []
    current_ref_index = 0
    num_sentences = len(sentences)
    for i, sent in enumerate(sentences, start=1):
        sent_words = normalize_text(sent)
        if not sent_words:
            continue
        sent_length = len(sent_words)
        try:
            start_ref_idx = ref_words.index(sent_words[0], current_ref_index)
        except ValueError:
            print(f"Warning: First word '{sent_words[0]}' of sentence {i} not found in transcript.")
            current_ref_index += sent_length
            continue
        end_ref_idx = start_ref_idx + sent_length - 1
        current_ref_index = end_ref_idx + 1
        hyp_indices = [ref_to_hyp_map[ri] for ri in range(start_ref_idx, end_ref_idx + 1) if ri in ref_to_hyp_map]
        if not hyp_indices:
            print(f"Warning: No alignment found for sentence {i}")
            continue
        min_hyp_idx = min(hyp_indices)
        max_hyp_idx = max(hyp_indices)
        recognized_chunk = recognized_words[min_hyp_idx:max_hyp_idx+1]
        recognized_length = len(recognized_chunk)
        if recognized_length > sent_length * 1.2:
            excess = recognized_length - sent_length
            recognized_chunk = recognized_chunk[:recognized_length - excess]
            max_hyp_idx = min_hyp_idx + len(recognized_chunk) - 1
        elif recognized_length < sent_length * 0.8:
            needed = int(sent_length - recognized_length)
            extend_end = max_hyp_idx + needed
            if extend_end < len(recognized_words):
                recognized_chunk = recognized_words[min_hyp_idx:extend_end+1]
                max_hyp_idx = extend_end
        start_time = recognized_chunk[0]['StartTimeSec']
        if i < num_sentences:
            next_sent_words = normalize_text(sentences[i])
            if next_sent_words:
                try:
                    next_start_ref_idx = ref_words.index(next_sent_words[0], end_ref_idx+1)
                    if next_start_ref_idx in ref_to_hyp_map:
                        next_first_hyp_idx = ref_to_hyp_map[next_start_ref_idx]
                        end_time = recognized_words[next_first_hyp_idx]['StartTimeSec']
                    else:
                        end_time = recognized_chunk[-1]['EndTimeSec']
                except ValueError:
                    end_time = recognized_chunk[-1]['EndTimeSec']
            else:
                end_time = recognized_chunk[-1]['EndTimeSec']
        else:
            end_time = recognized_chunk[-1]['EndTimeSec']
        sentence_segments.append((i, start_time, end_time, sent))

    # Step 5: Segment the full audio into individual sentence files (saved in segments_folder)
    segmented_files = []
    for (idx, start_time, end_time, ref_sentence) in sentence_segments:
        out_file = os.path.join(segments_folder, f"sentence{idx}.wav")
        # Calculate the duration for the segment
        duration = end_time - start_time
        ffmpeg_command = [
            "ffmpeg", "-y",
            "-ss", str(start_time),
            "-i", full_audio_filename,
            "-t", str(duration),
            "-c:a", "pcm_s16le",  # re-encode audio to WAV format
            out_file
        ]
        subprocess.run(ffmpeg_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        segmented_files.append((idx, out_file, ref_sentence))

    # Step 6: Run pronunciation assessment on each segmented sentence file
    with open(sentence_csv_file, 'w', newline='', encoding='utf-8') as sentence_csv, \
         open(word_csv_file, 'w', newline='', encoding='utf-8') as word_csv:
        sentence_writer = csv.writer(sentence_csv)
        word_writer     = csv.writer(word_csv)
        # Write headers
        sentence_writer.writerow([
            "sentence_index", "reference_text", "recognized_text",
            "accuracy_score", "prosody_score", "pronunciation_score",
            "completeness_score", "fluency_score"
        ])
        word_writer.writerow(["sentence_index", "word_index", "word", "accuracy_score", "error_type"])
        assess_speech_config = speechsdk.SpeechConfig(subscription=speech_key, region=service_region)
        assess_speech_config.set_property(speechsdk.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "3000")
        for (idx, wav_file, ref_sentence) in segmented_files:
            sentence_audio_config = speechsdk.audio.AudioConfig(filename=wav_file)
            pronunciation_config = speechsdk.PronunciationAssessmentConfig(
                reference_text=ref_sentence,
                grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
                granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
                enable_miscue=True
            )
            pronunciation_config.enable_prosody_assessment()
            sentence_recognizer = speechsdk.SpeechRecognizer(
                speech_config=assess_speech_config,
                language=language,
                audio_config=sentence_audio_config
            )
            pronunciation_config.apply_to(sentence_recognizer)
            result = sentence_recognizer.recognize_once_async().get()
            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                recognized_text = result.text
                pronunciation_result = speechsdk.PronunciationAssessmentResult(result)
                sentence_writer.writerow([
                    idx, ref_sentence, recognized_text,
                    pronunciation_result.accuracy_score,
                    pronunciation_result.prosody_score if pronunciation_result.prosody_score is not None else '',
                    pronunciation_result.pronunciation_score,
                    pronunciation_result.completeness_score,
                    pronunciation_result.fluency_score
                ])
                for j, w_info in enumerate(pronunciation_result.words, start=1):
                    word_writer.writerow([idx, j, w_info.word, w_info.accuracy_score, w_info.error_type])
            elif result.reason == speechsdk.ResultReason.NoMatch:
                print(f"No speech recognized for sentence {idx}.")
            elif result.reason == speechsdk.ResultReason.Canceled:
                cancellation_details = result.cancellation_details
                print(f"Recognition canceled for sentence {idx}: {cancellation_details.reason}")
                if cancellation_details.reason == speechsdk.CancellationReason.Error:
                    print("Error details: {}".format(cancellation_details.error_details))

    print("\nDone. CSV outputs saved as:")
    print(f"Sentence-level: {sentence_csv_file}")
    print(f"Word-level: {word_csv_file}")
    print(f"Segmented sentence audio files are located in: {segments_folder}")