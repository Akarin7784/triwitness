#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_SepalWidget.py::TestSepalWidget::test_get_children \
  tests/test_SepalWidget.py::TestSepalWidget::test_init \
  tests/test_SepalWidget.py::TestSepalWidget::test_set_viz \
  tests/test_SepalWidget.py::TestSepalWidget::test_show \
  tests/test_SepalWidget.py::TestSepalWidget::test_hide \
  tests/test_SepalWidget.py::TestSepalWidget::test_toggle_viz \
  tests/test_SepalWidget.py::TestSepalWidget::test_reset \
  tests/test_SepalWidget.py::TestSepalWidget::test_set_children \
  tests/test_SepalWidget.py::TestSepalWidget::test_set_children_error; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
