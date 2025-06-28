#!/bin/bash
cd `dirname $0`
konsole -e bash -c "rye run python ./audio_list.py"
