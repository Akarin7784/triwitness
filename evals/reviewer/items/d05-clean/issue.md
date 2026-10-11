`textkit.slugify("  Hello,  World!  ")` returns `"-hello-world-"`; expected `"hello-world"`.
Slugs should never start or end with `-`, and runs of separators should become a single `-`
(e.g. `"a -- b"` → `"a-b"`).
