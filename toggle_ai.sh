#!/usr/bin/env bash
# 1-Click AI Backend Toggle for Desktop Pet (Local Qwen2.5-VL <-> Cloud Google Gemini)
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
/home/shourya/miniconda3/envs/desktop-pet/bin/python "$DIR/pet-brain/scripts/toggle_ai.py"
