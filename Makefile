.PHONY: clean clean-all clean-clean clean-errors clean-logs clean-extracts

clean: clean-errors clean-logs

clean-all: clean-clean clean-extracts clean-errors clean-logs

clean-clean:
	rm -rf data/clean/*

clean-extracts:
	rm -rf data/extracts/*

clean-errors:
	rm -rf data/errors/*

clean-logs:
	rm -rf data/logs/*
