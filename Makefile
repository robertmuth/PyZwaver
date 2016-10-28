.PHONY: check_pylint check_pyflakes  tests

SHELL:=/bin/bash

PYTHON_SOURCES = pyzwaver/*.py tests/*.py  *.py
TD =  ./TestData

check_pylint:: 
	for i in $(PYTHON_SOURCES) ; do echo pylint: $$i ; pylint --rcfile pylint.conf -E $$i ; done

check_pyflakes::
	for i in $(PYTHON_SOURCES) ; do echo pyflakes: $$i ; pyflakes3 $$i ; done



# generate zwave.py file with all zwave constants
../pyzwaver/zwave.py: constants_generator.py
	./constants_generator.py python > $@


tests:
	@echo "run message parsing test"
	diff <(./zmessage_test.py < $(TD)/api_application_command.input.txt) $(TD)/api_application_command.golden.txt
	echo "run node test [9]"
	diff <(./znode_test.py < $(TD)/node.09.input.txt) $(TD)/node.09.golden.txt
	echo "run node test [10]"
	diff <(./znode_test.py < ${TD}/node.10.input.txt) $(TD)/node.10.golden.txt
	@echo "PASS"
