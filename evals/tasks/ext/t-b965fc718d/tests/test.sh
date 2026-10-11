#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  distributed/protocol/tests/test_protocol.py::test_fallback_to_pickle \
  distributed/protocol/tests/test_protocol.py::test_protocol \
  distributed/protocol/tests/test_protocol.py::test_small \
  distributed/protocol/tests/test_protocol.py::test_small_and_big \
  'distributed/protocol/tests/test_protocol.py::test_large_bytes[bytes]' \
  'distributed/protocol/tests/test_protocol.py::test_large_bytes[memoryview]' \
  distributed/protocol/tests/test_protocol.py::test_large_messages_map \
  distributed/protocol/tests/test_protocol.py::test_loads_deserialize_False \
  distributed/protocol/tests/test_protocol.py::test_dumps_loads_Serialize \
  distributed/protocol/tests/test_protocol.py::test_dumps_loads_Serialized \
  'distributed/protocol/tests/test_protocol.py::test_preserve_header[serializers0]' \
  'distributed/protocol/tests/test_protocol.py::test_preserve_header[serializers1]' \
  'distributed/protocol/tests/test_protocol.py::test_sizeof_serialize[Serialize-Serialized0]' \
  'distributed/protocol/tests/test_protocol.py::test_sizeof_serialize[Serialize-Serialized1]' \
  'distributed/protocol/tests/test_protocol.py::test_sizeof_serialize[ToPickle-Pickled]' \
  distributed/protocol/tests/test_protocol.py::test_deeply_nested_structures; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
