#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/search.py::test_delete_database \
  tests/search.py::test_reset_index \
  tests/search.py::test_search_dataset \
  tests/search.py::test_product_term \
  tests/search.py::test_searchable_database \
  tests/search.py::test_synonym_search \
  tests/search.py::test_categories_term \
  tests/search.py::test_delete_dataset \
  tests/search.py::test_search_with_special_chars \
  tests/search.py::test_limit \
  tests/search.py::test_copy_save_propogates_to_search_index \
  tests/search.py::test_update_dataset \
  tests/search.py::test_add_searchable_database \
  tests/search.py::test_add_datasets \
  tests/search.py::test_modify_database \
  tests/search.py::test_search_single_char \
  tests/search.py::test_basic_search \
  tests/search.py::test_star_search \
  tests/search.py::test_search_with_parentheses \
  tests/search.py::test_search_with_substrings \
  tests/search.py::test_search_geocollection_location \
  tests/search.py::test_add_database \
  tests/search.py::test_escape_search \
  tests/search.py::test_search_dataset_containing_stop_word \
  tests/search.py::test_add_dataset \
  tests/search.py::test_comment_term \
  tests/search.py::test_search_faceting \
  tests/search.py::test_case_sensitivity_convert_lowercase; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
