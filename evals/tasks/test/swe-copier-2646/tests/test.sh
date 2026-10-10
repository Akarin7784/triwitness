#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_cleanup.py::test_cleanup_on_interrupt_during_git_clone \
  tests/test_cleanup.py::test_no_cleanup_when_template_in_parent_folder \
  tests/test_cleanup.py::test_no_cleanup_when_folder_existed \
  tests/test_cleanup.py::test_do_not_cleanup \
  tests/test_cleanup.py::test_cleanup \
  tests/test_cleanup.py::test_cleanup_on_interrupt_during_copy_task \
  tests/test_cleanup.py::test_cleanup_on_interrupt_during_update_task; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
