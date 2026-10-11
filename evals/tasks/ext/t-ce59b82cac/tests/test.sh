#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  test/pagination_test.py::PaginationTest::test_nonpaginates_collection \
  test/pagination_test.py::PaginationTest::test_paginated_collection \
  test/pagination_test.py::PaginationTest::test_paginated_collection_iterator \
  test/pagination_test.py::PaginationTest::test_paginated_collection_no_cache \
  test/pagination_test.py::PaginationTest::test_paginated_iterator \
  test/pagination_test.py::PaginationTest::test_pagination_next_page \
  test/pagination_test.py::PaginationTest::test_pagination_previous; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
