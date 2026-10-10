#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_pqueues.py::TestDownloaderAwarePriorityQueue::test_tie_breaking_rotates_slots \
  tests/test_pqueues.py::TestDownloaderAwarePriorityQueue::test_tie_breaking_keeps_rotation_after_selected_slot_is_deleted \
  tests/test_pqueues.py::TestPriorityQueue::test_queue_push_pop_one \
  tests/test_pqueues.py::TestPriorityQueue::test_peek \
  tests/test_pqueues.py::TestPriorityQueue::test_queue_push_pop_priorities \
  tests/test_pqueues.py::TestDownloaderAwarePriorityQueue::test_push_pop \
  tests/test_pqueues.py::TestDownloaderAwarePriorityQueue::test_peek \
  'tests/test_pqueues.py::test_pop_order[input_0-output0]' \
  'tests/test_pqueues.py::test_pop_order[input_1-output1]' \
  'tests/test_pqueues.py::test_pop_order[input_2-output2]' \
  'tests/test_pqueues.py::test_pop_order[input_3-output3]' \
  'tests/test_pqueues.py::test_pop_order[input_4-output4]' \
  'tests/test_pqueues.py::test_pop_order[input_5-output5]'; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
