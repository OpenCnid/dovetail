---
name: nonascii-skill
description: Fixture with non-ASCII frontmatter — curly “quotes”, an em dash, CJK 中文测试, and U+2001 ( ) whose UTF-8 bytes include 0x81, undefined in cp1252.
---

# Non-ASCII fixture

Reading this file at the platform default encoding on Windows either raises
`UnicodeDecodeError` (0x81, 0x8D, 0x8F, 0x90, 0x9D have no cp1252 mapping) or
silently mojibakes the text. The packager must read it as UTF-8 explicitly.
