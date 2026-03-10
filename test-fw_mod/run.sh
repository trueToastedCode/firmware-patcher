#!/bin/bash
set -e
docker build -t thumb2_clamp_test .
docker run --rm thumb2_clamp_test

# Also extract the compiled ARM binary to local folder
docker create --name tmp_extract thumb2_clamp_test
docker cp tmp_extract:/test/test_clamp ./test_clamp
docker rm tmp_extract

echo ""
echo "Binary extracted to: $(pwd)/test_clamp"
