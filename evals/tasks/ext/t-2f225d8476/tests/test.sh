#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_conversions.py::test_code \
  tests/test_conversions.py::test_a \
  tests/test_conversions.py::test_a_spaces \
  tests/test_conversions.py::test_a_with_title \
  tests/test_conversions.py::test_a_shortcut \
  tests/test_conversions.py::test_a_no_autolinks \
  tests/test_conversions.py::test_a_in_code \
  tests/test_conversions.py::test_b \
  tests/test_conversions.py::test_b_spaces \
  tests/test_conversions.py::test_blockquote \
  tests/test_conversions.py::test_blockquote_with_nested_paragraph \
  tests/test_conversions.py::test_blockquote_with_paragraph \
  tests/test_conversions.py::test_blockquote_nested \
  tests/test_conversions.py::test_br \
  tests/test_conversions.py::test_dl \
  tests/test_conversions.py::test_del \
  tests/test_conversions.py::test_div_section_article \
  tests/test_conversions.py::test_em \
  tests/test_conversions.py::test_figcaption \
  tests/test_conversions.py::test_header_with_space \
  tests/test_conversions.py::test_h1 \
  tests/test_conversions.py::test_h2 \
  tests/test_conversions.py::test_hn \
  tests/test_conversions.py::test_hn_chained \
  tests/test_conversions.py::test_hn_nested_tag_heading_style \
  tests/test_conversions.py::test_hn_nested_simple_tag \
  tests/test_conversions.py::test_hn_nested_img \
  tests/test_conversions.py::test_hn_atx_headings \
  tests/test_conversions.py::test_hn_atx_closed_headings \
  tests/test_conversions.py::test_hn_newlines \
  tests/test_conversions.py::test_head \
  tests/test_conversions.py::test_hr \
  tests/test_conversions.py::test_i \
  tests/test_conversions.py::test_img \
  tests/test_conversions.py::test_video \
  tests/test_conversions.py::test_kbd \
  tests/test_conversions.py::test_p \
  tests/test_conversions.py::test_pre \
  tests/test_conversions.py::test_q \
  tests/test_conversions.py::test_script \
  tests/test_conversions.py::test_style \
  tests/test_conversions.py::test_s \
  tests/test_conversions.py::test_samp \
  tests/test_conversions.py::test_strong \
  tests/test_conversions.py::test_strong_em_symbol \
  tests/test_conversions.py::test_sub \
  tests/test_conversions.py::test_sup \
  tests/test_conversions.py::test_lang \
  tests/test_conversions.py::test_lang_callback \
  tests/test_conversions.py::test_spaces; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
