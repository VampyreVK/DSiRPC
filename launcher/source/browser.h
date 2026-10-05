// SPDX-License-Identifier: MIT
//
// A file picker on the bottom screen.

#ifndef BROWSER_H__
#define BROWSER_H__

#include <stdbool.h>
#include <stddef.h>

// Lets the user pick a file whose name ends in `extension` (e.g. ".nds"),
// starting in `start_dir` ("sd:/..."; the SD root if it can't be opened).
// `title` is shown at the top. Returns true with the full path in out, or
// false if the user backed out.
bool browse_for_file(const char *title, const char *start_dir, const char *extension,
                     char *out, size_t outsz);

#endif // BROWSER_H__
