#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/test_main.py::test_database_bom \
  tests/test_main.py::test_no_options \
  tests/test_main.py::test_sample \
  tests/test_main.py::test_sample_clobber_template \
  tests/test_main.py::test_sample_clobber_database \
  tests/test_main.py::test_sample_clobber_config \
  tests/test_main.py::test_defaults \
  tests/test_main.py::test_bad_limit \
  tests/test_main.py::test_limit_combo \
  tests/test_main.py::test_template_not_found \
  tests/test_main.py::test_database_not_found \
  tests/test_main.py::test_config_not_found \
  tests/test_main.py::test_help \
  tests/test_main.py::test_version \
  tests/test_main.py::test_bad_template \
  tests/test_main.py::test_bad_database \
  tests/test_main.py::test_bad_config \
  tests/test_main.py::test_attachment \
  tests/test_main.py::test_utf8_template \
  tests/test_main.py::test_utf8_database \
  tests/test_main.py::test_utf8_headers \
  tests/test_main.py::test_resume \
  tests/test_main.py::test_resume_too_small \
  tests/test_main.py::test_resume_too_big \
  tests/test_main.py::test_resume_hint_on_config_error \
  tests/test_main.py::test_resume_hint_on_csv_error \
  tests/test_main.py::test_other_mime_type; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
