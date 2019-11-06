#!/usr/bin/env nix-shell
#!nix-shell -i bash -p entr
echo "watching program for changes..."
while sleep 1 ; do
    find . -regex ".*\(midi2dt\.py\|configs\.json\)$" 2>/dev/null | entr -r ./midi2dt.py;
done

