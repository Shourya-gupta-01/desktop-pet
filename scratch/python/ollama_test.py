import requests
import json
import sys

OLLAMA_URL = "http://localhost:11434/api/generate"

def test_ollama(model_name, prompt):
    print(f"Testing {model_name}...")
    
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        print(f"[{model_name}] Response: {result['response']}\n")
    except requests.exceptions.ConnectionError:
        print(f"Failed to connect to Ollama at {OLLAMA_URL}. Is it running?")
        sys.exit(1)
    except Exception as e:
        print(f"Error testing {model_name}: {e}")

if __name__ == "__main__":
    # Test standard text generation
    test_ollama("mistral", "Say 'Hello from Ollama!' in exactly 4 words.")
    
    # Test multimodal vision (we'll just use mistral again if llava isn't available, but try llava first)
    # The user confirmed they have llava and mistral.
    test_ollama("llava", "Describe the color of a red apple.")
