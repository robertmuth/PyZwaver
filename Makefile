.PHONY: check_pylint check_pyflakes tests check

SHELL:=/bin/bash

PYTHON_SOURCES = pyzwaver/*.py tests/*.py  *.py
TD =  ./TestData
export PYTHONPATH = $(PWD)

check_pylint::
	@echo "============================================================"
	@echo "pylint checking"
	@echo "============================================================"
	@for i in $(PYTHON_SOURCES) ; do echo pylint: $$i ; pylint --rcfile pylint.conf -E $$i ; done

check_pyflakes::
	@echo "============================================================"
	@echo "pyflake checking"
	@echo "============================================================"
	@for i in $(PYTHON_SOURCES) ; do echo pyflakes: $$i ; pyflakes3 $$i ; done

check:: check_pylint check_pyflakes

# generate zwave.py file with all zwave constants
pyzwaver/zwave.py: constants_generator.py
	./constants_generator.py python > $@

tests:
	@echo "============================================================"
	@echo "run message parsing test"
	@echo "============================================================"
	cd Tests;./command_test.py < ../TestData/commands.input.txt
	@echo "============================================================"
	@echo "application node test"
	@echo "============================================================"
	cd Tests;./application_nodeset_test.py
	@echo "PASS"		

tests_obsolete:
	@echo "============================================================"
	@echo "run message parsing test"
	@echo "============================================================"
	diff <(./zmessage_test.py < $(TD)/api_application_command.input.txt) $(TD)/api_application_command.golden.txt
	@echo "============================================================"
	@echo "run node test [9]"
	@echo "============================================================"
	diff <(./znode_test.py < $(TD)/node.09.input.txt) $(TD)/node.09.golden.txt
	@echo "============================================================"
	@echo "run node test [10]"
	@echo "============================================================"
	diff <(./znode_test.py < ${TD}/node.10.input.txt) $(TD)/node.10.golden.txt
	@echo "PASS"
