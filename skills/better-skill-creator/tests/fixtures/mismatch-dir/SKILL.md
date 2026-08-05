---
name: totally-different-name
description: Fixture whose frontmatter name disagrees with its folder name. The packager must refuse it, because the archive's top-level directory is the folder name.
---

# Mismatch

Every install surface requires the archive's single top-level directory to
match the frontmatter `name`. This fixture violates that.
