#!/usr/bin/env bash
# 隐藏测试放到仓库外运行，Agent 看不到；结果写 Harbor 约定的 reward 文件。
cd /workspace/repo
mkdir -p /logs/verifier
cp /tests/test_parse.py /tmp/test_parse.py
if python -m pytest -q -p no:cacheprovider --rootdir=/workspace/repo --junitxml=/logs/verifier/junit.xml /tmp/test_parse.py; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
