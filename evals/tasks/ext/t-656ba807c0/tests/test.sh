#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  'tests/aggregation/test_ds_aggregation.py::test_aggregate_ds_gold_on_toy_ysda[10-0]' \
  'tests/aggregation/test_ds_aggregation.py::test_aggregate_ds_gold_on_toy_ysda[100500-1e-05]' \
  'tests/aggregation/test_ds_aggregation.py::test_aggregate_ds_on_toy_ysda[10-0]' \
  'tests/aggregation/test_ds_aggregation.py::test_aggregate_ds_on_toy_ysda[100500-1e-05]' \
  'tests/aggregation/test_ds_aggregation.py::test_aggregate_hds_on_toy_ysda[10-0]' \
  'tests/aggregation/test_ds_aggregation.py::test_aggregate_hds_on_toy_ysda[100500-1e-05]' \
  'tests/aggregation/test_ds_aggregation.py::test_aggregate_ds_on_simple[10-0]' \
  'tests/aggregation/test_ds_aggregation.py::test_aggregate_ds_on_simple[100500-1e-05]' \
  'tests/aggregation/test_ds_aggregation.py::test_aggregate_hds_on_simple[10-0]' \
  'tests/aggregation/test_ds_aggregation.py::test_aggregate_hds_on_simple[100500-1e-05]' \
  'tests/aggregation/test_ds_aggregation.py::test_dawid_skene_step_by_step[0]' \
  'tests/aggregation/test_ds_aggregation.py::test_dawid_skene_step_by_step[1]' \
  tests/aggregation/test_ds_aggregation.py::test_dawid_skene_on_empty_input \
  'tests/aggregation/test_ds_aggregation.py::test_dawid_skene_overlap[3]' \
  'tests/aggregation/test_ds_aggregation.py::test_dawid_skene_overlap[300]' \
  'tests/aggregation/test_ds_aggregation.py::test_dawid_skene_overlap[30000]' \
  tests/aggregation/test_ds_aggregation.py::test_ds_on_bool_labels \
  tests/aggregation/test_ds_aggregation.py::test_hds_on_bool_labels; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
