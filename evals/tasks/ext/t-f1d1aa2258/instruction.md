Duplicates should be stripped before saving a from a CountryField which has multiple=True
I'm using `CountrySelectWidget` in the admin interface, along with the following settings:
```python
COUNTRIES_FIRST = ['IE']
COUNTRIES_FIRST_REPEAT = True
```
This particular scenario leads to some unexpected behavior: When I select Ireland from _either_ the top section of the widget _or_ from the regular list and save the object, the model field will contain `[Country(code='IE')]` (as expected). When I then reopen the objects' change view, the widget will have _both_ Irelands selected and store `[Country(code='IE'), Country(code='IE')]` on a subsequent save.

From my point of view, rendering both Irelands as selected in the widget is acceptable since they point to the same country, but duplicating countries in the database is not. I suggest to strip the list of countries to be saved from duplicates.
