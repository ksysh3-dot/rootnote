#!/usr/bin/env bash
K='/mnt/c/Program Files/Android/Android Studio/plugins/Kotlin/kotlinc'
ls "$K/bin"; ls "$K/lib" | head -40; cat "$K/build.txt"
