#!/usr/bin/env bash
# Scaffold for this test: copies the profile in and seeds a fake library of folders
# the way a real Jellyfin movies directory looks (empty folders are enough for a shortlist).
set -eu
cp -R "$(dirname "$0")/files/." .
mkdir -p library
for t in "A Trip to the Moon (1902)" "Nosferatu (1922)" "The General (1926)" "Steamboat Willie (1928)" \
         "His Girl Friday (1940)" "Night of the Living Dead (1968)" "Big Buck Bunny (2008)" "Sintel (2010)" \
         "Tears of Steel (2012)" "Elephants Dream (2006)"; do mkdir -p "library/$t"; done
