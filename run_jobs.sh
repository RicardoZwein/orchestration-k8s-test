#!/bin/bash

MODE="$1"  # --send or --exec

if [[ "$MODE" == "--send" ]]; then
    echo "📬 Registering all jobs..."
    for filename in jobs/*.yaml; do
        py entrypoints/sender.py "$filename"
    done

elif [[ "$MODE" == "--exec" ]]; then
    echo "⚙️ Executing all jobs..."
    for filename in jobs/*.yaml; do
        py entrypoints/runner.py "$filename"
    done

else
    echo "❌ Usage: $0 [--send | --exec]"
    exit 1
fi
