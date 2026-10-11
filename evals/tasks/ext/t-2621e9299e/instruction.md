openapi3.errors.SpecError when minimum/maximum validation is float
The following file::

<details><summary><code>openapi.json</code></summary>

```json
{
    "openapi": "3.0.3",
    "info": {
        "title": "Foo",
        "version": "1.0.0"
    },
    "paths": {
        "/foo": {
            "post": {
                "responses": {
                    "200": {
                        "description": "Foo.",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "value": {
                                            "type": "number",
                                            "format": "double",
                                            "minimum": 0.0,
                                            "maximum": 1.0
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
```

</details>

Fails to load with the following error:


<details><summary>Traceback</summary>

```
Traceback (most recent call last):
  File "<censored>.py", line 5, in <module>
    api = OpenAPI(json.load(fd))
  File "<censored>/openapi.py", line 44, in __init__
    super(OpenAPI, self).__init__([], raw_document, self)
  File "<censored>/object_base.py", line 56, in __init__
    self._parse_data()
  File "<censored>/openapi.py", line 134, in _parse_data
    self.paths        = self._get('paths', ['Path'], is_map=True)
  File "<censored>/object_base.py", line 193, in _get
    ret = Map(self.path + [field], ret, object_types, self._root)
  File "<censored>/object_base.py", line 516, in __init__
    dct[k] = t(path + [k], v, self._root)
  File "<censored>/object_base.py", line 56, in __init__
    self._parse_data()
  File "<censored>/paths.py", line 36, in _parse_data
    self.post        = self._get('post', 'Operation')
  File "<censored>/object_base.py", line 209, in _get
    ret = python_type(self.path + [field], ret, self._root)
  File "<censored>/object_base.py", line 56, in __init__
    self._parse_data()
  File "<censored>/paths.py", line 102, in _parse_data
    self.responses    = self._get('responses', ['Response', 'Reference'], is_map=True)
  File "<censored>/object_base.py", line 193, in _get
    ret = Map(self.path + [field], ret, object_types, self._root)
  File "<censored>/object_base.py", line 516, in __init__
    dct[k] = t(path + [k], v, self._root)
  File "<censored>/object_base.py", line 56, in __init__
    self._parse_data()
  File "<censored>/paths.py", line 385, in _parse_data
    self.content     = self._get('content', ['MediaType'], is_map=True)
  File "<censored>/object_base.py", line 193, in _get
    ret = Map(self.path + [field], ret, object_types, self._root)
  File "<censored>/object_base.py", line 516, in __init__
    dct[k] = t(path + [k], v, self._root)
  File "<censored>/object_base.py", line 56, in __init__
    self._parse_data()
  File "<censored>/paths.py", line 365, in _parse_data
    self.schema   = self._get('schema', ['Schema', 'Reference'])
  File "<censored>/object_base.py", line 209, in _get
    ret = python_type(self.path + [field], ret, self._root)
  File "<censored>/object_base.py", line 56, in __init__
    self._parse_data()
  File "<censored>/schemas.py", line 50, in _parse_data
    self.properties           = self._get('properties', ['Schema', 'Reference'], is_map=True)
  File "<censored>/object_base.py", line 193, in _get
    ret = Map(self.path + [field], ret, object_types, self._root)
  File "<censored>/object_base.py", line 516, in __init__
    dct[k] = t(path + [k], v, self._root)
  File "<censored>/object_base.py", line 56, in __init__
    self._parse_data()
  File "<censored>/schemas.py", line 36, in _parse_data
    self.maximum              = self._get('maximum', int)
  File "<censored>/object_base.py", line 222, in _get
    raise SpecError('Expected {}.{} to be one of [{}], got {}'.format(
openapi3.errors.SpecError: Expected paths./foo.post.responses.200.content.application/json.schema.properties.value.maximum to be one of [<class 'int'>], got <class 'float'>
```

</details>

The specification reads ([section 5.2, validation schema](https://tools.ietf.org/html/draft-wright-json-schema-validation-00#section-5.2)):

> The value of "maximum" MUST be a number, representing an upper limit
> for a numeric instance.
> 
> If the instance is a number, then this keyword validates if
> "exclusiveMaximum" is true and instance is less than the provided
> value, or else if the instance is less than or exactly equal to the
> provided value.

The same happens with `minimum` (and probably the `exclusive*` variants, didn't bother to check).

A number is ([section 4.2, core schema](https://tools.ietf.org/html/draft-wright-json-schema-00#section-4.2)):

> number  An arbitrary-precision, base-10 decimal number value, from
> the JSON "number" production

Thus, the code should not be checking for `int` but `float`.
