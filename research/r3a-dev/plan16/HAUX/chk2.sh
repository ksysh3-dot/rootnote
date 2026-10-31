#!/bin/bash
cd ~/r3a-dev
echo "files newer than CHOICES.md outside HAUX (should be none):"
find . -newer plan16/HAUX/CHOICES.md -type f -not -path './plan16/HAUX/*' 2>/dev/null | head
cd ~/r3-work && git status --short | head -5
du -sh ~/r3a-dev/plan16/HAUX/* | sort -h | tail -8
