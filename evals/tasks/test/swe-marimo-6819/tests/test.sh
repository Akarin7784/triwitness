#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  tests/_save/test_external_decorators.py::TestAsExternalApp::test_as_external_app \
  tests/_save/test_external_decorators.py::TestAsExternalApp::test_as_external_app_in_kernel \
  tests/_save/test_external_decorators.py::TestAsExternalApp::test_as_external_app_embedded \
  tests/_save/test_external_decorators.py::TestAsExternalApp::test_as_external_app_embedded_cloned \
  tests/_save/test_external_decorators.py::TestDecoratorImports::test_import_alias_hash_path \
  tests/_save/test_external_decorators.py::TestDecoratorImports::test_has_shared_import \
  tests/_save/test_external_decorators.py::TestDecoratorImports::test_doesnt_have_shared_import \
  tests/_save/test_external_decorators.py::TestDecoratorImports::test_has_dep_with_differing_name_works \
  tests/_save/test_external_decorators.py::TestDecoratorImports::test_decorator_in_kernel \
  tests/_save/test_external_decorators.py::TestDecoratorTransitiveFns::test_impure_decorator_with_pure_dependencies \
  tests/_save/test_external_decorators.py::TestDecoratorTransitiveFns::test_pure_decorator_with_impure_dependencies \
  tests/_save/test_external_decorators.py::TestAsExternalApp::test_as_external_app_embedded_in_kernel; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
