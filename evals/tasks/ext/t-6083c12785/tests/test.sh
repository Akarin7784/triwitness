#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  pycytominer/tests/test_annotate.py::test_annotate_platemap_naming \
  pycytominer/tests/test_annotate.py::test_annotate_output \
  pycytominer/tests/test_annotate.py::test_annotate_output_compress \
  pycytominer/tests/test_annotate.py::test_annotate \
  pycytominer/tests/test_cyto_utils/test_cells.py::test_SingleCells_init \
  pycytominer/tests/test_cyto_utils/test_cells.py::test_SingleCells_reset_variables \
  pycytominer/tests/test_cyto_utils/test_cells.py::test_SingleCells_count \
  pycytominer/tests/test_cyto_utils/test_cells.py::test_aggregate_comparment \
  pycytominer/tests/test_cyto_utils/test_cells.py::test_aggregate_subsampling_count_cells \
  pycytominer/tests/test_cyto_utils/test_cells.py::test_aggregate_subsampling_profile \
  pycytominer/tests/test_cyto_utils/test_cells.py::test_aggregate_subsampling_profile_output \
  pycytominer/tests/test_cyto_utils/test_cells.py::test_aggregate_subsampling_profile_output_multiple_queries \
  pycytominer/tests/test_cyto_utils/test_cells.py::test_n_aggregation_memory_strata \
  pycytominer/tests/test_cyto_utils/test_cells.py::test_invalid_n_aggregation_memory_strata \
  pycytominer/tests/test_cyto_utils/test_cells.py::test_sqlite_strata_conditions \
  pycytominer/tests/test_cyto_utils/test_cells.py::test_aggregate_count_cells_multiple_strata \
  pycytominer/tests/test_cyto_utils/test_cells.py::test_add_image_features; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
