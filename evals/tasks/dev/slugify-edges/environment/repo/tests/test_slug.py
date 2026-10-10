from textkit import slugify


def test_simple():
    assert slugify("Hello World") == "hello-world"
