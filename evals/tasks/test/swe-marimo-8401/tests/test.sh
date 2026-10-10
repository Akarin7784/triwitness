#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/_ast/test_cell_manager.py::TestIsExternalCellId::test_bare_uuid_not_external \
  tests/_ast/test_cell_manager.py::TestCellManager::test_create_cell_id \
  tests/_ast/test_cell_manager.py::TestCellManager::test_register_cell \
  tests/_ast/test_cell_manager.py::TestCellManager::test_register_cell_auto_id \
  tests/_ast/test_cell_manager.py::TestCellManager::test_ensure_one_cell \
  tests/_ast/test_cell_manager.py::TestCellManager::test_cell_queries \
  tests/_ast/test_cell_manager.py::TestCellManager::test_get_cell_id_by_code \
  tests/_ast/test_cell_manager.py::TestCellManager::test_get_cell_code \
  tests/_ast/test_cell_manager.py::TestCellManager::test_get_cell_data \
  tests/_ast/test_cell_manager.py::TestCellManager::test_register_unparsable_cell \
  tests/_ast/test_cell_manager.py::TestCellManager::test_valid_cells \
  tests/_ast/test_cell_manager.py::TestCellManager::test_create_cell_id_1000 \
  tests/_ast/test_cell_manager.py::TestIsExternalCellId::test_normal_cell_id \
  tests/_ast/test_cell_manager.py::TestIsExternalCellId::test_embedded_cell_id \
  tests/_ast/test_cell_manager.py::TestIsExternalCellId::test_embedded_setup_cell_id \
  tests/_ast/test_cell_manager.py::TestIsExternalCellId::test_empty_string \
  tests/_ast/test_cell_manager.py::TestIsExternalCellId::test_non_uuid_long_string \
  tests/_ast/test_cell_manager.py::TestCellMatching::test_exact_matches \
  tests/_ast/test_cell_manager.py::TestCellMatching::test_reordered_codes \
  tests/_ast/test_cell_manager.py::TestCellMatching::test_similar_but_not_exact_matches \
  tests/_ast/test_cell_manager.py::TestCellMatching::test_similar_but_not_exact_matches_with_dupes \
  tests/_ast/test_cell_manager.py::TestCellMatching::test_left_inexact_matches_with_dupes \
  tests/_ast/test_cell_manager.py::TestCellMatching::test_right_inexact_matches_with_dupes \
  tests/_ast/test_cell_manager.py::TestCellMatching::test_outer_inexact_matches \
  tests/_ast/test_cell_manager.py::TestCellMatching::test_outer_inexact_matches_with_dupes \
  tests/_ast/test_cell_manager.py::TestCellMatching::test_fewer_next_cells \
  tests/_ast/test_cell_manager.py::TestCellMatching::test_more_next_cells \
  tests/_ast/test_cell_manager.py::TestCellMatching::test_completely_different_codes \
  tests/_ast/test_cell_manager.py::TestCellMatching::test_empty_lists \
  tests/_ast/test_cell_manager.py::TestCellMatching::test_empty_strings \
  tests/_ast/test_cell_manager.py::TestCellMatchingEdgeCases::test_multiple_identical_codes_in_prev \
  tests/_ast/test_cell_manager.py::TestCellMatchingEdgeCases::test_multiple_identical_codes_in_next \
  tests/_ast/test_cell_manager.py::TestCellMatchingEdgeCases::test_very_long_common_prefixes_suffixes \
  tests/_ast/test_cell_manager.py::TestCellMatchingEdgeCases::test_unicode_and_special_characters \
  tests/_ast/test_cell_manager.py::TestCellMatchingEdgeCases::test_mixed_case_sensitivity \
  tests/_ast/test_cell_manager.py::TestCellMatchingEdgeCases::test_whitespace_variations \
  tests/_ast/test_cell_manager.py::TestCellMatchingEdgeCases::test_all_codes_being_substrings \
  tests/_ast/test_cell_manager.py::TestCellMatchingEdgeCases::test_maximum_length_differences \
  tests/_ast/test_cell_manager.py::TestCellMatchingEdgeCases::test_empty_strings_edge_case \
  tests/_ast/test_cell_manager.py::TestCellMatchingEdgeCases::test_identical_codes \
  tests/_ast/test_cell_manager.py::TestCellMatchingEdgeCases::test_completely_different_codes_edge_case \
  tests/_ast/test_cell_manager.py::TestCellMatchingEdgeCases::test_special_python_syntax \
  tests/_ast/test_cell_manager.py::TestCellMatchingEdgeCases::test_similar_reduction \
  tests/_ast/test_cell_manager.py::TestSortCellIdsBySimilarity::test_simple_reorder \
  tests/_ast/test_cell_manager.py::TestSortCellIdsBySimilarity::test_reorder_same_ids \
  tests/_ast/test_cell_manager.py::TestSortCellIdsBySimilarity::test_less_cells \
  tests/_ast/test_cell_manager.py::TestSortCellIdsBySimilarity::test_more_cells \
  tests/_ast/test_cell_manager.py::TestSortCellIdsBySimilarity::test_similar_reduction \
  tests/_ast/test_cell_manager.py::TestSortCellIdsBySimilarity::test_code_map \
  tests/_ast/test_cell_manager.py::TestSortCellIdsBySimilarity::test_code_map_empty; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
