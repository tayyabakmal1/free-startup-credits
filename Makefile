# free-startup-credits
#
# Contributors normally need none of this: edit one file under data/programs/
# and open a pull request. CI runs everything below.

PY := python
SCRIPTS := scripts

.PHONY: help schema validate build links freshness audit social check

help:
	@echo "make schema    regenerate schema/program.schema.json from data/"
	@echo "make validate  schema + hygiene + duplicate checks over data/programs/"
	@echo "make build     regenerate schema, README, categories/, collections/, api/"
	@echo "make links     check every URL in data/ (needs lychee)"
	@echo "make freshness list entries due for re-verification"
	@echo "make audit     follow every URL and flag dead links and brand redirects"
	@echo "make social    regenerate the social preview card"
	@echo "make check     validate + build + fail if generated output drifted"

schema:
	@$(PY) $(SCRIPTS)/gen_schema.py
	@$(PY) $(SCRIPTS)/gen_issue_forms.py

validate: schema
	@$(PY) $(SCRIPTS)/validate.py
	@$(PY) $(SCRIPTS)/test_integrity.py

build: schema
	@$(PY) $(SCRIPTS)/build.py

# CI gate: regenerate everything and fail if the committed output differs.
check: validate build
	@git diff --exit-code -- README.md categories/ collections/ api/ schema/ \
	  || (echo ""; \
	      echo "ERROR: generated files are out of date."; \
	      echo "Run 'make build' and commit the result."; \
	      echo "Do not hand-edit README.md, categories/, collections/ or api/."; \
	      exit 1)

links:
	lychee --config lychee.toml --extensions yml,yaml data/

freshness:
	@$(PY) $(SCRIPTS)/freshness.py

audit:
	@$(PY) $(SCRIPTS)/audit_list.py --self

social:
	@$(PY) $(SCRIPTS)/gen_social_preview.py
