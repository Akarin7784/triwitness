DateField does not properly serialize datetime objects
When storing a Python `datetime` object in a property specified by a `DateField`, the value incorrectly serializes to an ISO timestamp (`YYYY-MM-DDThh:mm:ss`) instead of to a `xs:date` format (`YYYY-MM-DD`).

    class Foo(Entity):
        my_date = DateField("my_date");

    obj = Foo()
    obj.my_date = datetime.datetime.now()

There are two issues:

* the `DateField::binding_value` function uses `serialize_datetime` instead of `serialize_date`

* the `serialize_date` function erroneously includes time information in its output when processing datetimes
