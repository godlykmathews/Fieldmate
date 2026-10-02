#!/bin/zsh
cd "${0:A:h}"
if [ ! -x .venv/bin/python ]; then
  print "The project environment is missing. Follow the setup steps in README.md."
  read "reply?Press Enter to close."
  exit 1
fi
exec .venv/bin/python -m fieldmate
