#!/usr/bin/env bash
# 判分：用 test_patch 之后的测试文件覆盖仓库里的同名文件，只跑 FAIL_TO_PASS + PASS_TO_PASS；全部通过写 1。
set -u
cd /workspace/repo
mkdir -p /logs/verifier
cp -r /tests/files/. ./
if python -m pytest -q -p no:cacheprovider --junitxml=/logs/verifier/junit.xml \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::test_redirect_with_xss \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::testCookies \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::testDefaultContentType \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::testFavicon \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::testFlatten \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::testRanges \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::testRedirect \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::testSlashes \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::testStatus \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::test_InternalRedirect \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::test_cherrypy_url \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::test_expose_decorator \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::test_multiple_headers \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::test_on_end_resource_status \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::test_redirect_with_unicode \
  cherrypy/test/test_core.py::CoreRequestHandlingTest::test_gc \
  cherrypy/test/test_core.py::ErrorTests::test_contextmanager \
  cherrypy/test/test_core.py::ErrorTests::test_start_response_error \
  cherrypy/test/test_core.py::ErrorTests::test_gc \
  cherrypy/test/test_core.py::TestBinding::test_bind_ephemeral_port; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
