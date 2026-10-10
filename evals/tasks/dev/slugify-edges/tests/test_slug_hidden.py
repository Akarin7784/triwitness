from textkit import slugify


def test_simple():
    assert slugify("Hello World") == "hello-world"


def test_digits_kept():
    assert slugify("Python 3 12") == "python-3-12"


def test_strip_edges():
    assert slugify("  Hello,  World!  ") == "hello-world"


def test_collapse_separators():
    assert slugify("a -- b__c") == "a-b-c"


def test_only_symbols():
    assert slugify("!!!") == ""
