import os
import pyaudio
import wave
import speech_recognition as sr
import pyttsx3
import json
from datetime import datetime, timedelta
import threading

# Initialize text-to-speech engine
engine = pyttsx3.init()

# Directory to store course folders
BASE_DIR = "course_audios"
os.makedirs(BASE_DIR, exist_ok=True)

# Metadata file for storing user settings
SETTINGS_FILE = "user_settings.json"
if not os.path.exists(SETTINGS_FILE):
    with open(SETTINGS_FILE, "w") as f:
        json.dump({"first_time": True}, f)

# Global flag to control recording
stop_flag = threading.Event()

# Function to speak text
def speak(text):
    print(text)
    engine.say(text)
    engine.runAndWait()

# Function to recognize speech with retries
def recognize_speech(prompt=None):
    recognizer = sr.Recognizer()
    mic = sr.Microphone()

    if prompt:
        speak(prompt)

    with mic as source:
        recognizer.adjust_for_ambient_noise(source, duration=5)  # Adjusted for better detection
        while True:
            try:
                audio = recognizer.listen(source, timeout=5)  # Added timeout for better control
                text = recognizer.recognize_google(audio).lower()
                return text
            except sr.UnknownValueError:
                speak("I didn't capture that clearly. Could you please repeat?")
            except sr.RequestError:
                speak("Network error.")
                return None

# Function to check and handle first-time usage
def check_first_time():
    with open(SETTINGS_FILE, "r") as f:
        settings = json.load(f)

    if settings.get("first_time", True):
        speak("Welcome to the Course Audio Manager!")
        speak("This system helps you organize and manage your audio recordings by course.")
        speak("You can record, play, and access recordings easily.")
        speak("Let's get started!")

        settings["first_time"] = False
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f)

# Function to listen for the stop command in a separate thread
def listen_for_stop_command():
    while not stop_flag.is_set():
        command = recognize_speech()
        if "stop recording" in command:
            stop_flag.set()
            speak("Stopping recording.")

# Function to start recording
def record_audio(course_name, file_name):
    course_dir = os.path.join(BASE_DIR, course_name)
    os.makedirs(course_dir, exist_ok=True)

    file_path = os.path.join(course_dir, f"{file_name}.wav")  # Save without date and time
    chunk = 1024
    format = pyaudio.paInt16
    channels = 1
    rate = 44100

    p = pyaudio.PyAudio()
    stream = p.open(format=format, channels=channels, rate=rate, input=True, frames_per_buffer=chunk)

    speak("Recording started. Say 'stop recording' to end.")
    frames = []

    # Start a thread to listen for "stop recording"
    stop_flag.clear()
    listener_thread = threading.Thread(target=listen_for_stop_command, daemon=True)
    listener_thread.start()

    while not stop_flag.is_set():
        data = stream.read(chunk)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    with wave.open(file_path, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(p.get_sample_size(format))
        wf.setframerate(rate)
        wf.writeframes(b''.join(frames))

    speak("Recording stopped and saved.")

    # Prompt to play the recorded audio
    response = recognize_speech("Do you want to play the recorded file? Say 'yes' or 'no'.")
    if response == "yes":
        play_audio(course_name, file_name)
    else:
        speak("Returning to the main menu.")

# Function to play audio
def play_audio(course_name, file_name):
    file_path = os.path.join(BASE_DIR, course_name, f"{file_name}.wav")
    if not os.path.exists(file_path):
        speak(f"The file {file_name} does not exist in course {course_name}.")
        return

    speak(f"Playing {file_name} from course {course_name}.")
    chunk = 1024
    wf = wave.open(file_path, 'rb')

    p = pyaudio.PyAudio()
    stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True)

    data = wf.readframes(chunk)
    while data:
        stream.write(data)
        data = wf.readframes(chunk)

    stream.stop_stream()
    stream.close()
    p.terminate()

# Function to access and filter recordings
def access_content():
    courses = [folder for folder in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, folder))]
    if not courses:
        speak("No courses found.")
        return

    speak("The following courses are available:")
    for course in courses:
        speak(course)

    course_name = recognize_speech("Which course would you like to access?")
    if course_name not in courses:
        speak(f"Course {course_name} not found.")
        return

    speak("Do you want to filter recordings? Say 'yes' or 'no'.")
    response = recognize_speech()
    if response == "yes":
        filter_option = recognize_speech("Filter by natural terms like 'yesterday', 'last week', or specific weekdays.")

        course_dir = os.path.join(BASE_DIR, course_name)
        files = [f for f in os.listdir(course_dir) if f.endswith('.wav')]

        parsed_date = parse_date_term(filter_option)
        filtered_files = []

        if parsed_date:
            for file in files:
                try:
                    file_time = datetime.strptime(file.split('_')[1], "%Y-%m-%d").date()
                    if file_time == parsed_date.date():
                        filtered_files.append(file)
                except ValueError:
                    continue

        if filtered_files:
            speak("The following recordings are available:")
            for f in filtered_files:
                speak(f)

            file_name = recognize_speech("Which file would you like to play?")
            if file_name in filtered_files:
                play_audio(course_name, file_name)
            else:
                speak(f"File {file_name} not found.")
        else:
            speak("No files match the filter criteria.")
    else:
        speak("Returning to the main menu.")

# Helper to parse natural date terms
def parse_date_term(term):
    today = datetime.today()
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    if term == "yesterday":
        return today - timedelta(days=1)
    elif term == "last week":
        return today - timedelta(weeks=1)
    elif term in weekdays:
        delta_days = (today.weekday() - weekdays.index(term)) % 7
        return today - timedelta(days=delta_days)
    return None

# Main menu
def main_menu():
    check_first_time()  # Call to handle first-time usage

    while True:
        user_input = recognize_speech("Say 'record' to start recording, 'play' to play an audio, 'access content' to access content, or 'exit' to quit.")

        if user_input == "record":
            course_name = recognize_speech("Please say the course name.")
            file_name = recognize_speech("What should I name the file?")
            if course_name and file_name:
                record_audio(course_name, file_name)
        elif user_input == "play":
            course_name = recognize_speech("Please say the course name.")
            file_name = recognize_speech("What should I name the file?")
            play_audio(course_name, file_name)
        elif user_input == "access content":
            access_content()
        elif user_input == "exit":
            speak("Goodbye!")
            break
        else:
            speak("Invalid option. Please try again.")

if __name__ == "__main__":
    main_menu()