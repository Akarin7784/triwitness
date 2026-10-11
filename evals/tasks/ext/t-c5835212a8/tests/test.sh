#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/worksheet_test.py::WorksheetTest::test_update_works_with_swapped_values_and_range \
  tests/worksheet_test.py::WorksheetTest::test_acell \
  tests/worksheet_test.py::WorksheetTest::test_append_row \
  tests/worksheet_test.py::WorksheetTest::test_append_row_with_empty_value \
  tests/worksheet_test.py::WorksheetTest::test_append_row_with_empty_value_and_table_range \
  tests/worksheet_test.py::WorksheetTest::test_auto_resize_columns \
  tests/worksheet_test.py::WorksheetTest::test_basic_filters \
  tests/worksheet_test.py::WorksheetTest::test_batch_clear \
  tests/worksheet_test.py::WorksheetTest::test_batch_get \
  tests/worksheet_test.py::WorksheetTest::test_batch_update \
  tests/worksheet_test.py::WorksheetTest::test_cell \
  tests/worksheet_test.py::WorksheetTest::test_clear \
  tests/worksheet_test.py::WorksheetTest::test_clear_tab_color \
  tests/worksheet_test.py::WorksheetTest::test_copy_cut_range \
  tests/worksheet_test.py::WorksheetTest::test_delete_cols \
  tests/worksheet_test.py::WorksheetTest::test_delete_row \
  tests/worksheet_test.py::WorksheetTest::test_find \
  tests/worksheet_test.py::WorksheetTest::test_findall \
  tests/worksheet_test.py::WorksheetTest::test_format \
  tests/worksheet_test.py::WorksheetTest::test_freeze \
  tests/worksheet_test.py::WorksheetTest::test_get_all_records \
  tests/worksheet_test.py::WorksheetTest::test_get_all_records_different_header \
  tests/worksheet_test.py::WorksheetTest::test_get_all_records_duplicate_keys \
  tests/worksheet_test.py::WorksheetTest::test_get_all_records_expected_headers \
  tests/worksheet_test.py::WorksheetTest::test_get_all_records_numericise_unformatted \
  tests/worksheet_test.py::WorksheetTest::test_get_all_records_value_render_options \
  tests/worksheet_test.py::WorksheetTest::test_get_all_values \
  tests/worksheet_test.py::WorksheetTest::test_get_all_values_date_time_render_options \
  tests/worksheet_test.py::WorksheetTest::test_get_all_values_title_is_a1_notation \
  tests/worksheet_test.py::WorksheetTest::test_get_records \
  tests/worksheet_test.py::WorksheetTest::test_get_records_pad_more_than_one_key \
  tests/worksheet_test.py::WorksheetTest::test_get_records_pad_one_key \
  tests/worksheet_test.py::WorksheetTest::test_get_records_pad_values \
  tests/worksheet_test.py::WorksheetTest::test_get_records_wrong_rows_input \
  tests/worksheet_test.py::WorksheetTest::test_get_values_and_combine_merged_cells \
  tests/worksheet_test.py::WorksheetTest::test_get_values_and_maintain_size \
  tests/worksheet_test.py::WorksheetTest::test_get_values_merge_cells_outside_of_range \
  tests/worksheet_test.py::WorksheetTest::test_get_values_with_args_or_kwargs \
  tests/worksheet_test.py::WorksheetTest::test_group_columns \
  tests/worksheet_test.py::WorksheetTest::test_group_rows \
  tests/worksheet_test.py::WorksheetTest::test_hide_columns_rows \
  tests/worksheet_test.py::WorksheetTest::test_hide_gridlines \
  tests/worksheet_test.py::WorksheetTest::test_hide_show_worksheet \
  tests/worksheet_test.py::WorksheetTest::test_insert_cols \
  tests/worksheet_test.py::WorksheetTest::test_insert_row \
  tests/worksheet_test.py::WorksheetTest::test_range \
  tests/worksheet_test.py::WorksheetTest::test_range_get_all_values \
  tests/worksheet_test.py::WorksheetTest::test_range_reversed \
  tests/worksheet_test.py::WorksheetTest::test_range_unbounded \
  tests/worksheet_test.py::WorksheetTest::test_reorder_worksheets \
  tests/worksheet_test.py::WorksheetTest::test_resize \
  tests/worksheet_test.py::WorksheetTest::test_show_gridlines \
  tests/worksheet_test.py::WorksheetTest::test_sort \
  tests/worksheet_test.py::WorksheetTest::test_update_acell \
  tests/worksheet_test.py::WorksheetTest::test_update_and_get \
  tests/worksheet_test.py::WorksheetTest::test_update_cell \
  tests/worksheet_test.py::WorksheetTest::test_update_cell_multiline \
  tests/worksheet_test.py::WorksheetTest::test_update_cell_objects \
  tests/worksheet_test.py::WorksheetTest::test_update_cell_unicode \
  tests/worksheet_test.py::WorksheetTest::test_update_cells \
  tests/worksheet_test.py::WorksheetTest::test_update_cells_noncontiguous \
  tests/worksheet_test.py::WorksheetTest::test_update_cells_unicode \
  tests/worksheet_test.py::WorksheetTest::test_update_tab_color \
  tests/worksheet_test.py::WorksheetTest::test_update_title \
  tests/worksheet_test.py::WorksheetTest::test_worksheet_notes \
  tests/worksheet_test.py::WorksheetTest::test_worksheet_update_index; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
