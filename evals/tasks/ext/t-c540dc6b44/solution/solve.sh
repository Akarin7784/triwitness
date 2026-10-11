#!/usr/bin/env bash
# gold patch 之后的完整文件
set -euo pipefail
cd /workspace/repo
mkdir -p .
cat > setup.py <<'TW_EOF'
from setuptools import setup, find_packages
from os import path
from io import open


here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    readme = f.read()

with open(path.join(here, 'requirements.txt'), encoding='utf-8') as f:
    requires = [req.strip() for req in f if req]


setup(
    name='spectree',
    version='0.3.8',
    author='Keming Yang',
    author_email='kemingy94@gmail.com',
    description=('generate OpenAPI document and validate request&response '
                 'with Python annotations.'),
    long_description=readme,
    long_description_content_type='text/markdown',
    url='https://github.com/0b01001001/spectree',
    packages=find_packages(exclude=['examples*', 'tests*']),
    package_data={
    },
    classifiers=[
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    python_requires='>=3.6',
    install_requires=requires,
    extras_require={
        'flask': ['flask'],
        'falcon': ['falcon'],
        'starlette': ['starlette', 'requests'],
    },
    zip_safe=False,
    entry_points={
        'console_scripts': [],
    },
)
TW_EOF
mkdir -p spectree
cat > spectree/utils.py <<'TW_EOF'
import re
import inspect
import logging

# parse HTTP status code to get the code
HTTP_CODE = re.compile(r'^HTTP_(?P<code>\d{3})$')

logger = logging.getLogger(__name__)


def parse_comments(func):
    """
    parse function comments

    First line of comments will be saved as summary, and the rest
    will be saved as description.
    """
    doc = inspect.getdoc(func)
    if doc is None:
        return None, None
    doc = doc.split('\n', 1)
    if len(doc) == 1:
        return doc[0], None
    return doc[0], doc[1].strip()


def parse_request(func):
    """
    get json spec
    """
    data = {}
    if hasattr(func, 'json'):
        data = {
            'content': {
                'application/json': {
                    'schema': {
                        '$ref': f'#/components/schemas/{func.json}'
                    }
                }
            }
        }
    return data


def parse_params(func, params, models):
    """
    get spec for (query, headers, cookies)
    """
    if hasattr(func, 'query'):
        query = models[func.query]
        for name, schema in query['properties'].items():
            params.append({
                'name': name,
                'in': 'query',
                'schema': schema,
                'required': name in query.get('required', []),
                'description': schema.get('description', ''),
            })

    if hasattr(func, 'headers'):
        headers = models[func.headers]
        for name, schema in headers['properties'].items():
            params.append({
                'name': name,
                'in': 'header',
                'schema': schema,
                'required': name in headers.get('required', []),
                'description': schema.get('description', ''),
            })

    if hasattr(func, 'cookies'):
        cookies = models[func.cookies]
        for name, schema in cookies['properties'].items():
            params.append({
                'name': name,
                'in': 'cookie',
                'schema': schema,
                'required': name in cookies.get('required', []),
                'description': schema.get('description', ''),
            })

    return params


def parse_resp(func):
    """
    get the response spec

    If this function does not have explicit ``resp`` but have other models,
    a ``422 Validation Error`` will be append to the response spec. Since
    this may be triggered in the validation step.
    """
    responses = {}
    if hasattr(func, 'resp'):
        responses = func.resp.generate_spec()

    if '422' not in responses and has_model(func):
        responses['422'] = {'description': 'Validation Error'}

    return responses


def has_model(func):
    """
    return True if this function have ``pydantic.BaseModel``
    """
    if any(hasattr(func, x) for x in ('query', 'json', 'headers')):
        return True

    if hasattr(func, 'resp') and func.resp.has_model():
        return True

    return False


def parse_code(http_code):
    """
    get the code of this HTTP status

    :param str http_code: format like ``HTTP_200``
    """
    match = HTTP_CODE.match(http_code)
    if not match:
        return None
    return match.group('code')


def parse_name(func):
    """
    the func can be

        * undecorated functions
        * decorated functions
        * decorated class methods
    """
    return func.__name__


def default_before_handler(req, resp, req_validation_error, instance):
    """
    default handler called before the endpoint function after the request validation

    :param req: request provided by the web framework
    :param resp: response generated by SpecTree that will be returned
        if the validation error is not None
    :param req_validation_error: request validation error
    :param instance: class instance if the endpoint function is a class method
    """
    if req_validation_error:
        logger.info(
            '422 Validation Error',
            extra={
                'spectree_model': req_validation_error.model.__name__,
                'spectree_validation': req_validation_error.errors(),
            },
        )


def default_after_handler(req, resp, resp_validation_error, instance):
    """
    default handler called after the response validation

    :param req: request provided by the web framework
    :param resp: response from the endpoint function (if there is no validation error)
        or response validation error
    :param resp_validation_error: response validation error
    :param instance: class instance if the endpoint function is a class method
    """
    if resp_validation_error:
        logger.info(
            '500 Response Validation Error',
            extra={
                'spectree_model': resp_validation_error.model.__name__,
                'spectree_validation': resp_validation_error.errors(),
            },
        )
TW_EOF
