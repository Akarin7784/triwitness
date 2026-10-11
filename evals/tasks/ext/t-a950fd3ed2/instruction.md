[bug] `tools.build:defines` is broken in multiconfig setting
### Describe the bug

`tools.build:defines` is broken in multiconfig setting, e.g. with MSVC. The quoting in the generator expression is not correct in `blocks.py`.

### How to reproduce it

- Set `tools.build:defines=['A=1', 'B=2']`
- Observe how the generated toolchain file or afterwards generated vxproj by CMake does not contain the right definitions.

EDIT: See PR #15924 for more info
