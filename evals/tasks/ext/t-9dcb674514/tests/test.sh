#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  test/image_test.py::ImageTest::test_attach_image \
  test/image_test.py::ImageTest::test_create_image \
  test/image_test.py::ImageTest::test_create_image_then_add_parent_id \
  test/image_test.py::ImageTest::test_get_image \
  test/image_test.py::ImageTest::test_get_images \
  test/image_test.py::ImageTest::test_get_metafields_for_image; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
