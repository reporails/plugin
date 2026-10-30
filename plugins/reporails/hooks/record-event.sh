#!/bin/sh
# Hands each hook payload to an installed `ails hook --agent claude`.
# Never calls npx, never prints, always exits 0: recording must not affect the session.
here=$(cd "$(dirname "$0")" && pwd -P)
. "$here/ails-lookup.sh"
ails=$(ails_installed "$(cd "$here/../bin" && pwd -P)/ails")
if [ -n "$ails" ]; then
  "$ails" hook --agent claude >/dev/null 2>&1
else
  cat >/dev/null
fi
exit 0
