# Detect Operating System
ifdef OS
    PYTHON := python3.15.exe
    BIN_DIR := Scripts
    RM := rmdir /s /q
    CP := copy /y
else
    PYTHON := python3
    BIN_DIR := bin
    RM := rm -rf
    CP := cp
endif
export SPHINXBUILD   = ../.venv/builder/$(BIN_DIR)/sphinx-build

help:
	@echo "Please use 'make <target>' where <target> is one of:"
	@echo " black          Reformat the whole source code."
	@echo " clean          Remove all artifacts, including running containers and dangling volumes"
	@echo " cleancaches    Clean everything including all available caches."
	@echo " deploy         Deploy the whole dashboard, incl. database, importers etc."
	@echo " develop        Create a deployment, which automatically rebuilds and restarts a container once the source files have been edited."
	@echo " documentation  Rebuild the documentation for the Project."
	@echo " .env           Set up the environment variables needed for the docker compose / containers themself."
	@echo " dummy          Do nothing"

clean 0: 
	docker compose down -v
	-$(MAKE) -C ./documentation clean
	-$(RM) .venv

cleancaches cc: 0
	docker builder prune

black: .venv/builder/$(BIN_DIR)/activate
	.venv/builder/$(BIN_DIR)/black ./code/

deploy: .env
	docker compose up

develop d: .env
	docker compose up --build -w

documentation docu: .env .venv/builder/$(BIN_DIR)/activate
	$(MAKE) -C ./documentation singlehtml

dummy:
	@echo "I don't want to do anything today!"

.env: .env.sample
	@echo "The environment variables in the .env file have been set to the default values."
	@echo "You may want to change them according to your requirements."
	-$(CP) .env.sample .env

.venv/builder/$(BIN_DIR)/activate venv:
	-$(RM) .venv
	$(PYTHON) -m venv ./.venv/builder
	.venv/builder/$(BIN_DIR)/python -m pip install -U pip
	.venv/builder/$(BIN_DIR)/pip install -r code/builder/requirements.txt
