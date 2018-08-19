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
	./Tests/command_test.py < TestData/commands.input.txt
	#
	@echo "============================================================"
	@echo "application node test"
	@echo "============================================================"
	./Tests/application_nodeset_test.py
	#
	@echo "============================================================"
	@echo "Replay Test 09"
	@echo "============================================================"
	./Tests/replay_test.py  < TestData/node.09.input.txt > node.09.output.txt
	diff TestData/node.09.golden.txt  node.09.output.txt
	rm node.09.output.txt
	#
	@echo "============================================================"
	@echo "Replay Test 10"
	@echo "============================================================"
	./Tests/replay_test.py  < TestData/node.10.input.txt > node.10.output.txt
	diff TestData/node.10.golden.txt  node.10.output.txt
	rm node.10.output.txt
	#
	@echo "PASS"		

