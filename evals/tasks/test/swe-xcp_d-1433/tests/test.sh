#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  xcp_d/tests/test_utils_bids.py::test_collect_data_nibabies_ignore_t2w \
  xcp_d/tests/test_utils_bids.py::test_collect_data_nibabies_ignore_t1w \
  xcp_d/tests/test_utils_bids.py::test_collect_data_nibabies_t1w_only \
  xcp_d/tests/test_utils_bids.py::test_collect_data_nibabies_t2w_only \
  xcp_d/tests/test_utils_bids.py::test_collect_data_nibabies_no_t1w_t2w \
  xcp_d/tests/test_utils_bids.py::test_collect_data_nibabies_t1wspace_t2w \
  xcp_d/tests/test_utils_bids.py::test_collect_data_nibabies_t2wspace_t1w \
  xcp_d/tests/test_utils_bids.py::test_write_atlas_dataset_description \
  xcp_d/tests/test_utils_bids.py::test_get_entity \
  xcp_d/tests/test_utils_bids.py::test_group_across_runs; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
