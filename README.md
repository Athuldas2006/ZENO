# MyAI 🤖

A personal offline AI assistant built with Python, Ollama, Vosk and Moondream.

MyAI is designed to feel less like a formal chatbot and more like a personal assistant that runs locally on a Windows PC.

## ✨ Features

- 🧠 Local AI chat with **Ollama + Llama 3.2 3B**
- 🎤 Offline voice input with **Vosk**
- 🔊 Windows built-in text-to-speech
- 👀 Screen OCR with **Tesseract**
- 👁️ Local screen vision with **Moondream**
- 🪟 Windows active/open-window awareness
- 🧠 Conversation and personal-fact memory
- ⌨️ Global **Ctrl + Space** hotkey
- 💻 Runs in the background
- 🤐 Silent text-only mode
- 😎 Casual Gen-Z-style personality
- 🖥️ Lightweight Tkinter chat interface

## 🧩 Tech Stack

| Component | Technology |
|---|---|
| Language | Python |
| Text AI | Ollama + Llama 3.2 3B |
| Vision AI | Ollama + Moondream |
| Speech-to-text | Vosk |
| Text-to-speech | Windows System.Speech |
| OCR | Tesseract + PyTesseract |
| UI | Tkinter |
| Screen capture | Pillow |
| Global hotkey | keyboard |
| Memory | JSON |

## 🚀 Setup

### 1. Install Python

Install Python 3.10 or newer on Windows.

### 2. Install Ollama

Install Ollama and make sure it is running.

Then download the models:

```powershell
ollama pull llama3.2:3b
ollama pull moondream
```

### 3. Install Python dependencies

From the MyAI folder:

```powershell
pip install -r requirements.txt
```

> PyAudio can require a Windows-compatible wheel/build depending on your Python version.

### 4. Install Tesseract OCR

Install Tesseract OCR for Windows.

The current MyAI configuration expects it at:

```text
C:\Program Files\Tesseract-OCR\tesseract.exe
```

If yours is installed somewhere else, update `TESSERACT_PATH` in `myai.py`.

### 5. Download a Vosk model

Download a Vosk English model and extract it into the project folder as:

```text
MyAi/
└── vosk-model/
```

The Vosk model is intentionally **not included in this repository** because it is large.

### 6. Run MyAI

```powershell
python myai.py
```

MyAI starts in the background.

Press:

```text
Ctrl + Space
```

to wake the interface and start voice input.

## 📁 Project Structure

```text
MyAi/
├── myai.py
├── screen_test.py
├── start_myai.vbs
├── requirements.txt
├── .gitignore
├── Memory/          # local, ignored
├── vosk-model/      # local, ignored
├── Voice_test/      # local, ignored
└── PA/              # local, ignored
```

## 🔒 Privacy

MyAI is designed around local processing.

Conversation memory and personal facts are stored locally in the `Memory/` folder. That folder is ignored by Git so personal conversations are not uploaded to this repository.

Large local models are also ignored.

## ⚠️ Current Limitations

- Windows-focused
- Requires Ollama and local models
- Requires a Vosk speech model for voice input
- Screen vision only works with content that is currently visible
- Tesseract path may need to be changed for another installation
- The project is still under active development

## 🛠️ Status

MyAI is a personal project and is still being improved.

Planned improvements include a cleaner startup experience, faster interaction, more system controls and a more polished UI.

## 📄 License

This project is currently provided as a personal/portfolio project.
