import subprocess
import os
import sys
import requests

MODEL_URL = "https://huggingface.co/TheBloke/CodeLlama-7B-Instruct-GGUF/resolve/main/codellama-7b-instruct.Q4_K_M.gguf"
MODEL_FILENAME = "codellama-7b-instruct.Q4_K_M.gguf"
MODELS_DIR = "models"
REQUIREMENTS_FILE = "requirements.txt"

def install_requirements():
    print(f"Installing dependencies from {REQUIREMENTS_FILE}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_FILE])
        print("Dependencies installed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {e}")
        sys.exit(1)

def download_model():
    if not os.path.exists(MODELS_DIR):
        os.makedirs(MODELS_DIR)

    model_path = os.path.join(MODELS_DIR, MODEL_FILENAME)

    if os.path.exists(model_path):
        print(f"Model already exists at {model_path}. Skipping download.")
        return

    print(f"Downloading model from {MODEL_URL} to {model_path}...")
    try:
        with requests.get(MODEL_URL, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get('content-length', 0))
            block_size = 8192 # 8 Kibibytes
            downloaded_size = 0
            with open(model_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=block_size):
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    # Simple progress indicator
                    if total_size:
                        progress = int(50 * downloaded_size / total_size)
                        sys.stdout.write(f"\r[{'=' * progress}{' ' * (50 - progress)}] {downloaded_size / (1024*1024):.2f}MB / {total_size / (1024*1024):.2f}MB")
                        sys.stdout.flush()
            print("\nModel downloaded successfully.")
    except requests.exceptions.RequestException as e:
        print(f"Error downloading model: {e}")
        sys.exit(1)

def main():
    install_requirements()
    download_model()
    print("Setup complete. You can now run the CLI using: python run_cli.py")

if __name__ == "__main__":
    main()
