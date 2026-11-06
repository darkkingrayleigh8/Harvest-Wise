#!/usr/bin/env bash
echo "==================================================="
echo "  HarvestWise (AGR-06) Decision Engine Web App"
echo "==================================================="
if which xdg-open > /dev/null; then
  xdg-open frontend/index.html
elif which open > /dev/null; then
  open frontend/index.html
else
  python3 -m http.server 8080 --directory frontend
fi
