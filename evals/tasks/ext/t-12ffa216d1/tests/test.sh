#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/spellchecker_test.py::TestSpellChecker::test_add_word_priority \
  tests/spellchecker_test.py::TestSpellChecker::test_large_words \
  tests/spellchecker_test.py::TestSpellChecker::test_add_word \
  tests/spellchecker_test.py::TestSpellChecker::test_adding_unicode \
  tests/spellchecker_test.py::TestSpellChecker::test_bytes_input \
  tests/spellchecker_test.py::TestSpellChecker::test_candidates \
  tests/spellchecker_test.py::TestSpellChecker::test_capitalization_when_case_sensitive_defaults_to_false \
  tests/spellchecker_test.py::TestSpellChecker::test_capitalization_when_case_sensitive_true \
  tests/spellchecker_test.py::TestSpellChecker::test_capitalization_when_language_set \
  tests/spellchecker_test.py::TestSpellChecker::test_case_insensitive_parse_words \
  tests/spellchecker_test.py::TestSpellChecker::test_case_sensitive_parse_words \
  tests/spellchecker_test.py::TestSpellChecker::test_checking_odd_word \
  tests/spellchecker_test.py::TestSpellChecker::test_correction \
  tests/spellchecker_test.py::TestSpellChecker::test_edit_distance_invalud \
  tests/spellchecker_test.py::TestSpellChecker::test_edit_distance_one \
  tests/spellchecker_test.py::TestSpellChecker::test_edit_distance_one_property \
  tests/spellchecker_test.py::TestSpellChecker::test_edit_distance_two \
  tests/spellchecker_test.py::TestSpellChecker::test_extremely_large_words \
  tests/spellchecker_test.py::TestSpellChecker::test_import_export_gzip \
  tests/spellchecker_test.py::TestSpellChecker::test_import_export_json \
  tests/spellchecker_test.py::TestSpellChecker::test_iter_spellchecker \
  tests/spellchecker_test.py::TestSpellChecker::test_iter_word_frequency \
  tests/spellchecker_test.py::TestSpellChecker::test_language_list \
  tests/spellchecker_test.py::TestSpellChecker::test_load_external_dictionary \
  tests/spellchecker_test.py::TestSpellChecker::test_load_text_file \
  tests/spellchecker_test.py::TestSpellChecker::test_missing_dictionary \
  tests/spellchecker_test.py::TestSpellChecker::test_multiple_dicts \
  tests/spellchecker_test.py::TestSpellChecker::test_nan_correction \
  tests/spellchecker_test.py::TestSpellChecker::test_pop \
  tests/spellchecker_test.py::TestSpellChecker::test_pop_default \
  tests/spellchecker_test.py::TestSpellChecker::test_remove_by_threshold \
  tests/spellchecker_test.py::TestSpellChecker::test_remove_by_threshold_using_items \
  tests/spellchecker_test.py::TestSpellChecker::test_remove_word \
  tests/spellchecker_test.py::TestSpellChecker::test_remove_words \
  tests/spellchecker_test.py::TestSpellChecker::test_spanish_dict \
  tests/spellchecker_test.py::TestSpellChecker::test_split_words \
  tests/spellchecker_test.py::TestSpellChecker::test_tokenizer_file \
  tests/spellchecker_test.py::TestSpellChecker::test_tokenizer_provided \
  tests/spellchecker_test.py::TestSpellChecker::test_unique_words \
  tests/spellchecker_test.py::TestSpellChecker::test_unknown_words \
  tests/spellchecker_test.py::TestSpellChecker::test_word_contains \
  tests/spellchecker_test.py::TestSpellChecker::test_word_frequency \
  tests/spellchecker_test.py::TestSpellChecker::test_word_in \
  tests/spellchecker_test.py::TestSpellChecker::test_word_known \
  tests/spellchecker_test.py::TestSpellChecker::test_word_usage_frequency \
  tests/spellchecker_test.py::TestSpellChecker::test_words \
  tests/spellchecker_test.py::TestSpellChecker::test_words_more_complete; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
