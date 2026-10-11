lua.decode('"--3"') fails
This looks like a bug in the string parsing to me - as if the parser tries to detect comments inside literal strings.

`'--3'` is a perfectly valid lua string, of course.
