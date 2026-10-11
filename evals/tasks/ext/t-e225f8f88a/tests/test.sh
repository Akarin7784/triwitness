#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_text2num \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_text2num \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_alpha2digit_decimals \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_alpha2digit_formal \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_alpha2digit_integers \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_alpha2digit_ordinals \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_alpha2digit_signed \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_alpha2digit_zero \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_and \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_one_as_noun_or_article \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_relaxed \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_second_as_time_unit_vs_ordinal \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_text2num \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_text2num_centuries \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_text2num_exc \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_text2num_zeroes \
  tests/test_text_to_num_de.py::TestTextToNumDE::test_uppercase \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_alpha2digit_decimals \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_alpha2digit_formal \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_alpha2digit_integers \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_alpha2digit_ordinals \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_alpha2digit_ordinals_force \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_alpha2digit_signed \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_alpha2digit_zero \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_and \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_one_as_noun_or_article \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_relaxed \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_second_as_time_unit_vs_ordinal \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_text2num_centuries \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_text2num_exc \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_text2num_zeroes \
  tests/test_text_to_num_en.py::TestTextToNumEN::test_uppercase \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_alpha2digit_all_ordinals \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_alpha2digit_decimals \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_alpha2digit_formal \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_alpha2digit_integers \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_alpha2digit_ordinals \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_alpha2digit_signed \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_alpha2digit_zero \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_article \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_relaxed \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_text2num_centuries \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_text2num_exc \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_text2num_variants \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_text2num_zeroes \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_trente_et_onze \
  tests/test_text_to_num_fr.py::TestTextToNumFR::test_un_pronoun; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
