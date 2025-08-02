#!/bin/bash
cd `dirname $0`
konsole -e bash -c "rye run python ./audio_sync_rsync.py ; echo "Complete." ; read -n 1 -s -r -p \"Press any key to exit...\" ; echo"

