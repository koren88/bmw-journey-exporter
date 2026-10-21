.DEFAULT_GOAL := help
SHELL := /bin/sh
PYTHON ?= python3
export YEAR MONTH FROM TO OUTPUT SERIAL TIMEZONE PAUSE MAX_PAGES KEEP_AWAKE KEEP_CAPTURE KEEP_DEBUG FORMATS INPUT INPUTS CONFLICT BMW_MAKE_DRY_RUN

.PHONY: help setup doctor capture resume report merge test

help:
	@printf '%s\n' \
	  'BMW Journey Exporter common commands' \
	  '' \
	  '  make setup                                      Create .venv and install Python project dependencies' \
	  '  make doctor [SERIAL=...]                       Check ADB/device/screen through Docker' \
	  '  make capture YEAR=2026 [TIMEZONE=...]          Capture a year' \
	  '  make capture MONTH=2026-10 [OUTPUT=...]        Capture one month' \
	  '  make capture FROM=2026-09 TO=2026-10           Capture an inclusive range' \
	  '  make resume OUTPUT=./capture [overrides...]    Resume saved selection/settings by default' \
	  '  make report INPUT=./capture [FORMATS=...]      Generate selected reports offline (default xlsx)' \
	  '  make merge INPUTS="a:b" OUTPUT=./merged        Merge captures offline; colon separates paths' \
	  '  make test                                       Run offline tests' \
	  '' \
	  'Capture options: OUTPUT, SERIAL, TIMEZONE, PAUSE, MAX_PAGES, KEEP_AWAKE, FORMATS, KEEP_CAPTURE, KEEP_DEBUG.' \
	  'Run make setup only for local Python use; Docker capture does not need host Python.'

setup:
	@./make-cli.sh setup

doctor:
	@./make-cli.sh doctor

capture:
	@./make-cli.sh capture

resume:
	@./make-cli.sh resume

report:
	@./make-cli.sh report

merge:
	@./make-cli.sh merge

test:
	@./make-cli.sh test
