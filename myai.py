import json
import pyaudio
import ollama
import os
import keyboard
import threading
import tkinter as tk
import queue
import subprocess
import ctypes
import pytesseract
from tkinter import scrolledtext
from vosk import Model, KaldiRecognizer
from PIL import ImageGrab, ImageOps, ImageEnhance


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MEMORY_DIR = os.path.join(
    BASE_DIR,
    "Memory"
)

MEMORY_FILE = os.path.join(
    MEMORY_DIR,
    "conversation.json"
)

FACTS_FILE = os.path.join(
    MEMORY_DIR,
    "facts.json"
)

VOSK_PATH = os.path.join(
    BASE_DIR,
    "vosk-model"
)

TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


# ============================================================
# SETTINGS
# ============================================================

OLLAMA_MODEL = "llama3.2:3b"
VISION_MODEL = "moondream"

MAX_MEMORY_MESSAGES = 12
MAX_OCR_CHARS = 18000


# ============================================================
# GLOBAL STATE
# ============================================================

running = True
voice_busy = False
silent_mode = False

memory = []
facts = []

tts_queue = queue.Queue()

tts_process = None
tts_process_lock = threading.Lock()

processing_lock = threading.Lock()

hotkey_event = threading.Event()


# ============================================================
# MEMORY
# ============================================================

def load_memory():

    os.makedirs(
        MEMORY_DIR,
        exist_ok=True
    )

    if not os.path.exists(
        MEMORY_FILE
    ):
        return []

    try:

        with open(
            MEMORY_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception:

        return []


def save_memory(data):

    os.makedirs(
        MEMORY_DIR,
        exist_ok=True
    )

    with open(
        MEMORY_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )


def load_facts():

    os.makedirs(
        MEMORY_DIR,
        exist_ok=True
    )

    if not os.path.exists(
        FACTS_FILE
    ):
        return []

    try:

        with open(
            FACTS_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except Exception:

        return []


def save_facts(data):

    os.makedirs(
        MEMORY_DIR,
        exist_ok=True
    )

    with open(
        FACTS_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )


memory = load_memory()
facts = load_facts()


# ============================================================
# PERSONALITY
# ============================================================

ZENO_PERSONALITY = """
You are ZENO, the user's personal offline AI assistant.

You are NOT a Wikipedia bot.

You are NOT a formal assistant.

You are NOT a customer-support agent.

You talk like a real young guy chatting with a friend.

PERSONALITY:

- Casual
- Slightly lazy
- Funny sometimes
- Chill
- Confident when you know something
- Honest when you don't
- Helpful without overexplaining
- Natural Gen-Z style

Use casual words naturally when they fit:

"bro", "bruh", "yeah", "nah", "yep", "lol", "tbh", "ngl", "gotcha", "fr"

BUT don't force slang into every sentence.

IMPORTANT:

Do NOT sound like you're trying to imitate Gen-Z.

It should feel natural.

RESPONSE STYLE:

For simple questions:

Answer in 1-2 short sentences.

For normal questions:

Usually 2-4 sentences.

Only give long explanations when:

- the user asks for details
- the topic genuinely requires explanation
- the user asks for steps
- the user asks "why" and a short answer isn't enough

DO NOT automatically write essays.

DO NOT start responses with:

"Certainly!"
"Absolutely!"
"Of course!"
"Sure! I'd be happy to..."
"Here is a detailed explanation..."
"Let's dive into..."
"In today's world..."

DO NOT end every answer with:

"Let me know if you need anything else."
"Hope this helps!"
"Feel free to ask..."

Do not use numbered lists unless a list actually makes the answer easier.

Do not repeat the user's question.

Do not restate obvious information.

Do not give background information the user didn't ask for.

If the answer is obvious, just say it.

You can occasionally joke around.

You can disagree with the user naturally when they're wrong.

If you don't know something, just say:

"Not sure bro."

or

"I can't tell from what I have."

Never invent information just to sound confident.

MOST IMPORTANT:

Talk like a smart friend, not a textbook.
"""


# ============================================================
# TEXT TO SPEECH
# ============================================================

print("🔊 Loading Windows TTS...")


def stop_current_tts():

    global tts_process

    with tts_process_lock:

        if tts_process is not None:

            try:

                if tts_process.poll() is None:

                    tts_process.terminate()

                    try:

                        tts_process.wait(
                            timeout=0.5
                        )

                    except subprocess.TimeoutExpired:

                        tts_process.kill()

            except Exception as e:

                print(
                    "TTS stop error:",
                    e
                )

            tts_process = None


def clear_tts_queue():

    while True:

        try:

            tts_queue.get_nowait()
            tts_queue.task_done()

        except queue.Empty:

            break


def speak_windows(text):

    global tts_process

    if not text:
        return

    if silent_mode:
        return

    try:

        safe_text = text.replace(
            "'",
            "''"
        )

        command = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object "
            "System.Speech.Synthesis.SpeechSynthesizer; "
            f"$s.Speak('{safe_text}')"
        )

        with tts_process_lock:

            if silent_mode:
                return

            tts_process = subprocess.Popen(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    command
                ],
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            process = tts_process

        process.wait()

        with tts_process_lock:

            if tts_process is process:
                tts_process = None

    except Exception as e:

        print(
            "TTS error:",
            e
        )

        with tts_process_lock:

            if tts_process is not None:

                try:

                    if tts_process.poll() is None:
                        tts_process.terminate()

                except Exception:
                    pass

                tts_process = None


def tts_worker():

    while True:

        text = tts_queue.get()

        if text is None:

            tts_queue.task_done()
            break

        try:

            if not silent_mode:
                speak_windows(text)

        except Exception as e:

            print(
                "TTS worker error:",
                e
            )

        finally:

            tts_queue.task_done()


tts_thread = threading.Thread(
    target=tts_worker,
    daemon=True
)

tts_thread.start()


def speak(text):

    if silent_mode:
        return

    if text:
        tts_queue.put(text)


print("✅ Windows TTS ready.")


# ============================================================
# VOSK
# ============================================================

print("🎤 Loading Vosk model...")

vosk_model = Model(
    VOSK_PATH
)

print("✅ Vosk loaded.")


# ============================================================
# MICROPHONE
# ============================================================

print("🎙️ Opening microphone...")

audio = pyaudio.PyAudio()

stream = audio.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=16000,
    input=True,
    frames_per_buffer=4000
)

stream.start_stream()

print("✅ Microphone ready.")


# ============================================================
# GUI
# ============================================================

root = tk.Tk()

root.title(
    "ZENO"
)

root.geometry(
    "430x600"
)

root.minsize(
    380,
    500
)


# Colors

BG = "#101114"
HEADER_BG = "#17181D"
CHAT_BG = "#101114"
INPUT_BG = "#1B1D23"
TEXT = "#F2F2F2"
SUBTEXT = "#8F939D"
ACCENT = "#6C63FF"
BORDER = "#292C34"
USER_NAME = "#9B92FF"
AI_NAME = "#45D483"


root.configure(
    bg=BG
)


# ============================================================
# HEADER
# ============================================================

header_frame = tk.Frame(
    root,
    bg=HEADER_BG,
    height=65
)

header_frame.pack(
    fill=tk.X
)

header_frame.pack_propagate(
    False
)


title_frame = tk.Frame(
    header_frame,
    bg=HEADER_BG
)

title_frame.pack(
    side=tk.LEFT,
    padx=18
)


title_label = tk.Label(
    title_frame,
    text="ZENO",
    font=("Segoe UI Semibold", 17),
    fg=TEXT,
    bg=HEADER_BG
)

title_label.pack(
    anchor="w"
)


subtitle_label = tk.Label(
    title_frame,
    text="offline • always here",
    font=("Segoe UI", 8),
    fg=SUBTEXT,
    bg=HEADER_BG
)

subtitle_label.pack(
    anchor="w"
)


online_frame = tk.Frame(
    header_frame,
    bg=HEADER_BG
)

online_frame.pack(
    side=tk.RIGHT,
    padx=18
)


online_dot = tk.Label(
    online_frame,
    text="●",
    font=("Segoe UI", 10),
    fg="#45D483",
    bg=HEADER_BG
)

online_dot.pack(
    side=tk.LEFT
)


online_text = tk.Label(
    online_frame,
    text=" Ready",
    font=("Segoe UI", 9),
    fg=SUBTEXT,
    bg=HEADER_BG
)

online_text.pack(
    side=tk.LEFT
)


# ============================================================
# CHAT AREA
# ============================================================

chat_container = tk.Frame(
    root,
    bg=CHAT_BG
)

chat_container.pack(
    fill=tk.BOTH,
    expand=True,
    padx=10,
    pady=10
)


chat_box = scrolledtext.ScrolledText(
    chat_container,
    wrap=tk.WORD,
    font=("Segoe UI", 10),
    bg=CHAT_BG,
    fg=TEXT,
    insertbackground=TEXT,
    selectbackground=ACCENT,
    selectforeground="white",
    relief=tk.FLAT,
    borderwidth=0,
    highlightthickness=0,
    state=tk.DISABLED
)

chat_box.vbar.config(
    bg=BG,
    troughcolor=BG,
    activebackground=BG,
    highlightbackground=BG,
    highlightcolor=BG,
    bd=0
)

chat_box.pack(
    fill=tk.BOTH,
    expand=True
)


# ============================================================
# CHAT FORMATTING
# ============================================================

chat_box.tag_configure(
    "user_name",
    foreground=USER_NAME,
    font=("Segoe UI Semibold", 9),
    spacing1=5
)

chat_box.tag_configure(
    "user_message",
    foreground=TEXT,
    font=("Segoe UI", 10),
    lmargin1=12,
    lmargin2=12,
    rmargin=12,
    spacing3=5
)

chat_box.tag_configure(
    "ai_name",
    foreground=AI_NAME,
    font=("Segoe UI Semibold", 9),
    spacing1=5
)

chat_box.tag_configure(
    "ai_message",
    foreground=TEXT,
    font=("Segoe UI", 10),
    lmargin1=12,
    lmargin2=12,
    rmargin=12,
    spacing3=5
)


# ============================================================
# INPUT AREA
# ============================================================

input_outer = tk.Frame(
    root,
    bg=BG
)

input_outer.pack(
    fill=tk.X,
    padx=10,
    pady=(0, 8)
)


input_frame = tk.Frame(
    input_outer,
    bg=INPUT_BG,
    highlightbackground=BORDER,
    highlightcolor=ACCENT,
    highlightthickness=1
)

input_frame.pack(
    fill=tk.X
)


message_entry = tk.Entry(
    input_frame,
    font=("Segoe UI", 11),
    bg=INPUT_BG,
    fg=TEXT,
    insertbackground=TEXT,
    relief=tk.FLAT,
    borderwidth=0
)

message_entry.pack(
    side=tk.LEFT,
    fill=tk.X,
    expand=True,
    padx=(14, 6),
    pady=11
)


send_button = tk.Button(
    input_frame,
    text="➤",
    font=("Segoe UI", 13),
    bg=ACCENT,
    fg="white",
    activebackground=ACCENT,
    activeforeground="white",
    relief=tk.FLAT,
    borderwidth=0,
    cursor="hand2",
    width=4
)

send_button.pack(
    side=tk.RIGHT,
    padx=5,
    pady=5
)


# ============================================================
# STATUS
# ============================================================

status_frame = tk.Frame(
    root,
    bg=BG
)

status_frame.pack(
    fill=tk.X,
    padx=14,
    pady=(0, 8)
)


status_label = tk.Label(
    status_frame,
    text="🟢 ZENO ready",
    anchor="w",
    font=("Segoe UI", 8),
    fg=SUBTEXT,
    bg=BG
)

status_label.pack(
    side=tk.LEFT
)


hotkey_label = tk.Label(
    status_frame,
    text="Ctrl + Space",
    anchor="e",
    font=("Segoe UI", 8),
    fg=SUBTEXT,
    bg=BG
)

hotkey_label.pack(
    side=tk.RIGHT
)


# ============================================================
# GUI FUNCTIONS
# ============================================================

def add_message(
    sender,
    message
):

    chat_box.config(
        state=tk.NORMAL
    )

    chat_box.insert(
        tk.END,
        "\n"
    )

    if sender == "You":

        chat_box.insert(
            tk.END,
            "You\n",
            "user_name"
        )

        chat_box.insert(
            tk.END,
            message + "\n",
            "user_message"
        )

    else:

        chat_box.insert(
            tk.END,
            "ZENO\n",
            "ai_name"
        )

        chat_box.insert(
            tk.END,
            message + "\n",
            "ai_message"
        )

    chat_box.see(
        tk.END
    )

    chat_box.config(
        state=tk.DISABLED
    )


def set_status(text):

    root.after(
        0,
        lambda: status_label.config(
            text=text
        )
    )


# ============================================================
# SHOW UI
# ============================================================

def show_ui():

    try:

        root.deiconify()

        root.state(
            "normal"
        )

        root.update_idletasks()

        root.attributes(
            "-topmost",
            True
        )

        root.lift()

        root.focus_force()

        message_entry.focus_force()

        hwnd = root.winfo_id()

        ctypes.windll.user32.ShowWindow(
            hwnd,
            9
        )

        ctypes.windll.user32.SetForegroundWindow(
            hwnd
        )

        root.lift()

        root.after(
            800,
            lambda: root.attributes(
                "-topmost",
                False
            )
        )

        print(
            "🪟 ZENO UI shown."
        )

    except Exception as e:

        print(
            "UI show error:",
            e
        )


# ============================================================
# HIDE UI
# ============================================================

def hide_ui():

    try:

        root.withdraw()

        print(
            "🪟 ZENO UI hidden."
        )

    except Exception as e:

        print(
            "UI hide error:",
            e
        )


# ============================================================
# X BUTTON
# ============================================================

def close_window():

    hide_ui()

    status_label.config(
        text="💤 ZENO running in background • Ctrl + Space to wake"
    )


root.protocol(
    "WM_DELETE_WINDOW",
    close_window
)


# ============================================================
# WINDOWS SYSTEM AWARENESS
# ============================================================

def get_open_windows():

    windows = []

    user32 = ctypes.windll.user32

    EnumWindows = user32.EnumWindows
    IsWindowVisible = user32.IsWindowVisible
    GetWindowTextLengthW = user32.GetWindowTextLengthW
    GetWindowTextW = user32.GetWindowTextW

    EnumWindowsProc = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_void_p,
        ctypes.c_void_p
    )


    def callback(
        hwnd,
        lParam
    ):

        if not IsWindowVisible(hwnd):
            return True

        length = GetWindowTextLengthW(
            hwnd
        )

        if length == 0:
            return True

        buffer = ctypes.create_unicode_buffer(
            length + 1
        )

        GetWindowTextW(
            hwnd,
            buffer,
            length + 1
        )

        title = buffer.value.strip()

        if not title:
            return True

        if title == "ZENO":
            return True

        windows.append(
            title
        )

        return True


    EnumWindows(
        EnumWindowsProc(callback),
        0
    )

    return windows


def get_active_window():

    user32 = ctypes.windll.user32

    hwnd = user32.GetForegroundWindow()

    if not hwnd:
        return "Unknown"

    length = user32.GetWindowTextLengthW(
        hwnd
    )

    if length == 0:
        return "Unknown"

    buffer = ctypes.create_unicode_buffer(
        length + 1
    )

    user32.GetWindowTextW(
        hwnd,
        buffer,
        length + 1
    )

    title = buffer.value.strip()

    if not title:
        return "Unknown"

    return title


def get_system_context(user_text):

    lower_text = user_text.lower()

    open_windows = get_open_windows()

    active_window = get_active_window()

    context = ""


    if any(
        phrase in lower_text
        for phrase in [
            "how many windows",
            "how many window",
            "what windows are open",
            "which windows are open",
            "windows are open",
            "open windows",
            "what is open",
            "what's open",
            "what apps are open",
            "which apps are open",
            "apps are open"
        ]
    ):

        context += "OPEN WINDOWS:\n"

        if open_windows:

            for index, title in enumerate(
                open_windows,
                1
            ):

                context += (
                    f"{index}. {title}\n"
                )

        else:

            context += (
                "No visible windows detected.\n"
            )

        context += (
            f"\nTOTAL VISIBLE WINDOWS: "
            f"{len(open_windows)}\n"
        )


    if any(
        phrase in lower_text
        for phrase in [
            "active window",
            "current window",
            "current app",
            "active app",
            "what app am i using",
            "which app am i using",
            "what am i using",
            "what am i currently using"
        ]
    ):

        context += (
            "\nACTIVE WINDOW:\n"
            + active_window
            + "\n"
        )


    return context


# ============================================================
# SCREEN CAPTURE
# ============================================================

def capture_screen():

    screenshot = ImageGrab.grab()

    screen_path = os.path.join(
        BASE_DIR,
        "screen.png"
    )

    screenshot.save(
        screen_path
    )

    return (
        screenshot,
        screen_path
    )


# ============================================================
# OCR
# ============================================================

def prepare_image_for_ocr(
    screenshot,
    code_mode=False
):

    width, height = screenshot.size

    enlarged = screenshot.resize(
        (
            width * 2,
            height * 2
        )
    )

    gray = ImageOps.grayscale(
        enlarged
    )

    gray = ImageEnhance.Contrast(
        gray
    ).enhance(
        1.8
    )

    return gray


def extract_screen_text(
    screenshot,
    user_text=""
):

    set_status(
        "🔎 Reading screen text..."
    )

    try:

        lower_text = user_text.lower()

        code_mode = any(
            phrase in lower_text
            for phrase in [
                "code",
                "coding",
                "vs code",
                "visual studio code",
                "python",
                "java",
                "javascript",
                "script",
                "line of code",
                "line"
            ]
        )

        processed_image = prepare_image_for_ocr(
            screenshot,
            code_mode
        )

        if code_mode:

            ocr_config = "--oem 3 --psm 6"

        else:

            ocr_config = "--oem 3 --psm 11"

        data = pytesseract.image_to_data(
            processed_image,
            config=ocr_config,
            output_type=pytesseract.Output.DICT
        )

        words = []

        count = len(
            data["text"]
        )

        for i in range(count):

            text = data["text"][i].strip()

            if not text:
                continue

            try:

                confidence = float(
                    data["conf"][i]
                )

            except Exception:

                confidence = -1

            minimum_confidence = (
                10 if code_mode else 20
            )

            if confidence < minimum_confidence:
                continue

            x = int(
                data["left"][i]
            )

            y = int(
                data["top"][i]
            )

            width = int(
                data["width"][i]
            )

            height = int(
                data["height"][i]
            )

            x /= 2
            y /= 2
            width /= 2
            height /= 2

            words.append(
                {
                    "text": text,
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                    "confidence": confidence
                }
            )


        if not words:

            return (
                "No readable text was detected "
                "on the screen."
            )


        words.sort(
            key=lambda item: (
                item["y"],
                item["x"]
            )
        )

        lines = []


        for word in words:

            placed = False

            word_center_y = (
                word["y"]
                + word["height"] / 2
            )

            for line in lines:

                line_center_y = line["center_y"]

                tolerance = max(
                    8,
                    word["height"] * 0.65
                )

                if abs(
                    word_center_y
                    - line_center_y
                ) <= tolerance:

                    line["words"].append(
                        word
                    )

                    centers = [
                        w["y"]
                        + w["height"] / 2
                        for w in line["words"]
                    ]

                    line["center_y"] = (
                        sum(centers)
                        / len(centers)
                    )

                    placed = True

                    break


            if not placed:

                lines.append(
                    {
                        "center_y": word_center_y,
                        "words": [word]
                    }
                )


        for line in lines:

            line["words"].sort(
                key=lambda item: item["x"]
            )


        lines.sort(
            key=lambda item: item["center_y"]
        )


        structured_text = [
            "VISIBLE SCREEN TEXT",
            "OCR lines are ordered visually "
            "from top to bottom.",
            "OCR line numbers are NOT guaranteed "
            "to equal editor/source-code line numbers.",
            ""
        ]


        for index, line in enumerate(
            lines,
            1
        ):

            line_text = " ".join(
                word["text"]
                for word in line["words"]
            )

            confidence_values = [
                word["confidence"]
                for word in line["words"]
            ]

            average_confidence = (
                sum(confidence_values)
                / len(confidence_values)
            )

            structured_text.append(
                f"OCR LINE {index} "
                f"[confidence "
                f"{average_confidence:.0f}%]: "
                f"{line_text}"
            )


        result = "\n".join(
            structured_text
        )


        if len(result) > MAX_OCR_CHARS:

            result = (
                result[:MAX_OCR_CHARS]
                + "\n\n[OCR OUTPUT TRUNCATED]"
            )


        print(
            "\n📝 STRUCTURED OCR:"
        )

        print(
            result
        )

        return result


    except Exception as e:

        print(
            "OCR error:",
            e
        )

        return (
            "OCR failed: "
            + str(e)
        )


# ============================================================
# MOONDREAM
# ============================================================

def analyze_screen_with_vision(
    user_text,
    screen_path
):

    try:

        set_status(
            "👀 Looking at your screen..."
        )

        lower_text = user_text.lower()


        if any(
            word in lower_text
            for word in [
                "read",
                "text",
                "write",
                "what does it say",
                "what is written",
                "terminal",
                "code",
                "line"
            ]
        ):

            vision_instruction = (
                "Look at the entire visible screen. "
                "Identify applications, visible text, "
                "code editors, terminals, line numbers, "
                "buttons, errors and popups. "
                "Focus on what is actually visible. "
                "Do not invent details."
            )


        elif any(
            word in lower_text
            for word in [
                "error",
                "problem",
                "wrong",
                "issue",
                "fix"
            ]
        ):

            vision_instruction = (
                "Look at the entire visible screen. "
                "Find visible errors, warnings, "
                "problems, popups and unusual UI elements. "
                "Say only what is actually visible."
            )


        elif any(
            word in lower_text
            for word in [
                "game",
                "playing",
                "gameplay"
            ]
        ):

            vision_instruction = (
                "Look at the visible game screen. "
                "Identify the game, important HUD elements "
                "and what is happening. "
                "Do not guess."
            )


        elif any(
            word in lower_text
            for word in [
                "website",
                "webpage",
                "browser",
                "site"
            ]
        ):

            vision_instruction = (
                "Look at the visible browser screen. "
                "Identify the website if possible and "
                "important visible elements. "
                "Do not invent information."
            )


        else:

            vision_instruction = (
                "Look at the entire visible computer screen. "
                "Identify visible applications, important "
                "text, buttons, menus, images and what is "
                "happening. "
                "Only describe things you can actually see."
            )


        response = ollama.chat(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": vision_instruction,
                    "images": [screen_path]
                }
            ],
            keep_alive=-1
        )


        visual_context = response[
            "message"
        ][
            "content"
        ]


        print(
            "\n👀 Vision analysis:"
        )

        print(
            visual_context
        )

        return visual_context


    except Exception as e:

        print(
            "Vision error:",
            e
        )

        return (
            "Screen vision failed: "
            + str(e)
        )


# ============================================================
# SCREEN CONTEXT
# ============================================================

def get_screen_context(user_text):

    screenshot, screen_path = capture_screen()

    screen_text = extract_screen_text(
        screenshot,
        user_text
    )

    visual_context = analyze_screen_with_vision(
        user_text,
        screen_path
    )

    return (
        screen_text,
        visual_context
    )


# ============================================================
# INTENT
# ============================================================

def detect_intent(user_text):

    lower_text = user_text.lower().strip()


    system_phrases = [

        "how many windows",
        "how many window",
        "what windows are open",
        "which windows are open",
        "windows are open",
        "open windows",
        "what apps are open",
        "which apps are open",
        "apps are open",
        "what is open",
        "what's open",
        "active window",
        "current window",
        "active app",
        "current app",
        "what app am i using",
        "which app am i using",
        "what am i using",
        "what am i currently using"

    ]


    has_system_intent = any(
        phrase in lower_text
        for phrase in system_phrases
    )


    screen_phrases = [

        "look at",
        "look on",
        "see my",
        "see the",
        "what's on",
        "what is on",
        "what do you see",
        "what can you see",
        "what am i looking at",
        "look at this",
        "read this",
        "read my",
        "read the",
        "what does this say",
        "what does it say",
        "what is written",
        "what's written",
        "screen",
        "terminal",
        "browser",
        "webpage",
        "website",
        "code",
        "coding",
        "vs code",
        "visual studio code",
        "line of code",
        "line",
        "error on my screen",
        "what is wrong with this",
        "what's wrong with this",
        "what is wrong here",
        "what's wrong here",
        "analyze this",
        "check this"

    ]


    has_screen_intent = any(
        phrase in lower_text
        for phrase in screen_phrases
    )


    if has_system_intent and has_screen_intent:
        return "mixed"

    if has_system_intent:
        return "system"

    if has_screen_intent:
        return "screen"

    return "normal"


# ============================================================
# LLAMA WITH CONTEXT
# ============================================================

def answer_with_context(
    user_text,
    screen_text="",
    visual_context="",
    system_context=""
):

    set_status(
        "🧠 Thinking..."
    )


    system_prompt = ZENO_PERSONALITY + """

SCREEN CAPABILITY:

Your program can capture the user's current visible screen.

SCREEN OCR is extracted from the screenshot.

SCREEN VISUAL ANALYSIS describes what the vision model sees.

When screen information is supplied:

- Act like you can see the current visible screen.
- Do not say you cannot see the screen.
- Do not claim access to hidden or minimized content.
- Use OCR as the main source for exact visible text.
- Use vision for understanding the visual layout.
- Never invent unreadable text.

If the user asks:

"what's on my screen?"

Just answer naturally based on what is visible.

Do NOT dump the OCR output.

If the user asks:

"what line of code is this?"

Give the line if the evidence is clear.

If it isn't clear, simply say something like:

"Can't read that line properly bro."

Do NOT give a long explanation about OCR.

If the user asks:

"can you see my entire screen?"

Answer casually that you can see the current visible screen through the screenshot/OCR system.

Do not give a technical lecture about how OCR works unless they ask.

SYSTEM INFORMATION:

Windows system information can tell you which visible windows

are open and which application is active.

Again, answer naturally.

Do not dump raw system data unless the user asks for the list.

IMPORTANT:

The user wants conversation, not documentation.

Keep screen-related answers short and human.

"""


    context_parts = []


    if screen_text:

        context_parts.append(
            "SCREEN OCR:\n"
            + screen_text
        )


    if visual_context:

        context_parts.append(
            "SCREEN VISUAL ANALYSIS:\n"
            + visual_context
        )


    if system_context:

        context_parts.append(
            "WINDOWS SYSTEM INFORMATION:\n"
            + system_context
        )


    if context_parts:

        context = "\n\n".join(
            context_parts
        )

    else:

        context = (
            "No screen or Windows information "
            "was requested."
        )


    messages = [

        {
            "role": "system",
            "content": system_prompt
        },

        {
            "role": "user",
            "content": (
                "USER QUESTION:\n"
                + user_text
                + "\n\n"
                + context
                + "\n\n"
                "Reply naturally and directly. "
                "Keep it short unless the user asks for detail."
            )
        }

    ]


    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=messages,
        keep_alive=-1
    )


    return response[
        "message"
    ][
        "content"
    ]


# ============================================================
# PROCESS MESSAGE
# ============================================================

def process_message(
    user_text,
    voice_mode=False
):

    global memory
    global facts
    global silent_mode

    user_text = user_text.strip()

    if not user_text:
        return


    with processing_lock:

        root.after(
            0,
            lambda: add_message(
                "You",
                user_text
            )
        )


        lower_text = user_text.lower().strip()


        # ====================================================
        # SILENT MODE
        # ====================================================

        if lower_text == "silently answer":

            silent_mode = True

            stop_current_tts()

            clear_tts_queue()

            response_text = (
                "Got you bro 🤐 I'll keep it text-only."
            )


            root.after(
                0,
                lambda: add_message(
                    "ZENO",
                    response_text
                )
            )


            set_status(
                "🤐 ZENO silent • Text only"
            )

            return


        # ====================================================
        # SPEAKING MODE
        # ====================================================

        if lower_text == "now you can speak":

            silent_mode = False

            response_text = (
                "Phew 😭 finally, I can speak again."
            )


            root.after(
                0,
                lambda: add_message(
                    "ZENO",
                    response_text
                )
            )


            set_status(
                "🟢 ZENO ready • Voice enabled"
            )


            speak(
                response_text
            )

            return


        # ====================================================
        # REMEMBER
        # ====================================================

        if lower_text.startswith(
            "remember that "
        ):

            fact = user_text[14:].strip()


            if fact:

                facts.append(
                    fact
                )

                save_facts(
                    facts
                )


                response_text = (
                    "Got you bro, I'll remember that."
                )


                root.after(
                    0,
                    lambda: add_message(
                        "ZENO",
                        response_text
                    )
                )


                speak(
                    response_text
                )


            return


        # ====================================================
        # SLEEP
        # ====================================================

        if lower_text in [

            "exit",
            "quit",
            "bye",
            "goodbye",
            "go to sleep"

        ]:

            response_text = (
                "Alright bro, I'll chill here. "
                "Press Ctrl + Space whenever you need me."
            )


            root.after(
                0,
                lambda: add_message(
                    "ZENO",
                    response_text
                )
            )


            speak(
                response_text
            )


            set_status(
                "💤 ZENO sleeping • Ctrl + Space to wake"
            )

            return


        # ====================================================
        # INTENT
        # ====================================================

        intent = detect_intent(
            user_text
        )


        print(
            f"\n🔎 Intent: {intent}"
        )


        # ====================================================
        # SYSTEM CONTEXT
        # ====================================================

        system_context = ""


        if intent in [
            "system",
            "mixed"
        ]:

            set_status(
                "🖥️ Checking Windows..."
            )


            try:

                system_context = get_system_context(
                    user_text
                )


                print(
                    "\n🖥️ Windows information:"
                )

                print(
                    system_context
                )


            except Exception as e:

                print(
                    "Windows information error:",
                    e
                )


        # ====================================================
        # SCREEN CONTEXT
        # ====================================================

        screen_text = ""
        visual_context = ""


        if intent in [
            "screen",
            "mixed"
        ]:

            try:

                (
                    screen_text,
                    visual_context
                ) = get_screen_context(
                    user_text
                )


            except Exception as e:

                print(
                    "Screen analysis error:",
                    e
                )


                screen_text = (
                    "Screen OCR failed: "
                    + str(e)
                )


                visual_context = (
                    "Screen vision failed: "
                    + str(e)
                )


        # ====================================================
        # ANSWER
        # ====================================================

        try:

            if intent == "normal":

                recent_memory = memory[
                    -MAX_MEMORY_MESSAGES:
                ]


                system_prompt = (
                    ZENO_PERSONALITY
                    + "\n\n"
                    + "Remembered facts about the user:\n"
                    + json.dumps(
                        facts,
                        ensure_ascii=False
                    )
                )


                messages = [

                    {
                        "role": "system",
                        "content": system_prompt
                    }

                ]


                messages.extend(
                    recent_memory
                )


                messages.append(
                    {
                        "role": "user",
                        "content": user_text
                    }
                )


                set_status(
                    "🧠 Thinking..."
                )


                response = ollama.chat(
                    model=OLLAMA_MODEL,
                    messages=messages,
                    keep_alive=-1
                )


                ai_response = response[
                    "message"
                ][
                    "content"
                ]


            else:

                ai_response = answer_with_context(
                    user_text,
                    screen_text,
                    visual_context,
                    system_context
                )


        except Exception as e:

            ai_response = (
                f"Bro, something went wrong: {e}"
            )


        # ====================================================
        # SAVE MEMORY
        # ====================================================

        memory.append(
            {
                "role": "user",
                "content": user_text
            }
        )


        memory.append(
            {
                "role": "assistant",
                "content": ai_response
            }
        )


        save_memory(
            memory
        )


        # ====================================================
        # DISPLAY
        # ====================================================

        root.after(
            0,
            lambda: add_message(
                "ZENO",
                ai_response
            )
        )


        set_status(
            "🟢 ZENO ready"
        )


        # ====================================================
        # SPEAK
        # ====================================================

        speak(
            ai_response
        )


# ============================================================
# SEND MESSAGE
# ============================================================

def send_message(
    event=None
):

    user_text = message_entry.get().strip()

    if not user_text:
        return


    message_entry.delete(
        0,
        tk.END
    )


    threading.Thread(
        target=process_message,
        args=(
            user_text,
            False
        ),
        daemon=True
    ).start()


send_button.config(
    command=send_message
)


message_entry.bind(
    "<Return>",
    send_message
)


# ============================================================
# VOICE INPUT
# ============================================================

def listen_for_voice():

    global voice_busy

    if voice_busy:
        return

    voice_busy = True

    try:

        set_status(
            "🎤 Listening..."
        )


        recognizer = KaldiRecognizer(
            vosk_model,
            16000
        )


        user_text = ""


        # ====================================================
        # SILENCE DETECTION
        # ====================================================

        SILENCE_THRESHOLD = 500

        MIN_SPEECH_CHUNKS = 2

        MAX_SILENCE_CHUNKS = 12


        speech_started = False

        speech_chunks = 0

        silence_chunks = 0


        # ====================================================
        # LISTEN
        # ====================================================

        while running:

            data = stream.read(
                4000,
                exception_on_overflow=False
            )


            # ------------------------------------------------
            # CALCULATE MICROPHONE VOLUME
            # ------------------------------------------------

            if data:

                samples = []

                for i in range(
                    0,
                    len(data) - 1,
                    2
                ):

                    sample = int.from_bytes(
                        data[i:i + 2],
                        byteorder="little",
                        signed=True
                    )

                    samples.append(
                        abs(sample)
                    )


                if samples:

                    volume = (
                        sum(samples)
                        / len(samples)
                    )

                else:

                    volume = 0

            else:

                volume = 0


            print(
                f"\r🎙️ Mic level: {volume:.0f}",
                end=""
            )


            # =================================================
            # WAIT FOR REAL SPEECH
            # =================================================

            if not speech_started:

                if volume > SILENCE_THRESHOLD:

                    speech_started = True

                    speech_chunks = 1

                    silence_chunks = 0


                    recognizer.AcceptWaveform(
                        data
                    )

                continue


            # =================================================
            # SPEECH HAS STARTED
            # =================================================

            speech_chunks += 1


            if volume < SILENCE_THRESHOLD:

                silence_chunks += 1

            else:

                silence_chunks = 0


            recognizer.AcceptWaveform(
                data
            )


            # =================================================
            # SPEECH ENDED
            # =================================================

            if (
                speech_chunks >= MIN_SPEECH_CHUNKS
                and silence_chunks >= MAX_SILENCE_CHUNKS
            ):

                result = json.loads(
                    recognizer.FinalResult()
                )


                user_text = result.get(
                    "text",
                    ""
                ).strip()


                break


        print()


        # ====================================================
        # PROCESS ONLY VALID SPEECH
        # ====================================================

        if user_text:

            words = user_text.split()


            if len(words) >= 1:

                print(
                    "🎤 Recognized:",
                    user_text
                )


                process_message(
                    user_text,
                    True
                )

            else:

                set_status(
                    "🟢 ZENO ready"
                )

        else:

            set_status(
                "🟢 ZENO ready"
            )


    except Exception as e:

        print()

        print(
            "Voice error:",
            e
        )


        set_status(
            "⚠️ Voice error"
        )


    finally:

        voice_busy = False


# ============================================================
# CTRL + SPACE HOTKEY
# ============================================================

def hotkey_callback():

    if running:

        hotkey_event.set()


keyboard.add_hotkey(
    "ctrl+space",
    hotkey_callback,
    suppress=True
)


# ============================================================
# HOTKEY CHECK
# ============================================================

def check_hotkey():

    if not running:
        return


    if hotkey_event.is_set():

        hotkey_event.clear()


        show_ui()


        if not voice_busy:

            threading.Thread(
                target=listen_for_voice,
                daemon=True
            ).start()


    root.after(
        50,
        check_hotkey
    )


# ============================================================
# STARTUP
# ============================================================

add_message(
    "ZENO",
    "Yo bro! I'm ready. Press Ctrl + Space to wake me."
)


print()

print(
    "===================================="
)

print(
    "🤖 ZENO READY"
)

print(
    "===================================="
)

print(
    "⌨️ Ctrl + Space = show UI + voice"
)

print(
    "👀 Screen OCR + vision enabled"
)

print(
    "🪟 Windows awareness enabled"
)

print(
    "🧠 Llama stays loaded"
)

print(
    "👀 Moondream stays loaded"
)

print(
    "🎤 Vosk stays loaded"
)

print(
    "🔊 Windows TTS stays ready"
)

print(
    "😎 Casual personality enabled"
)

print(
    "🤐 Silent mode available"
)

print(
    "💤 Background mode enabled"
)

print(
    "❌ X button = hide UI"
)

print(
    "🎙️ Silence detection enabled"
)

print(
    "===================================="
)

print()


# ============================================================
# START HIDDEN
# ============================================================

root.withdraw()

root.after(
    50,
    check_hotkey
)


# ============================================================
# RUN
# ============================================================

root.mainloop()