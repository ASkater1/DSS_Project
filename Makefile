# Variables

help:
	@echo "Please use 'make <target>' where <target> is one of:"
	@echo "   clean               Remove all artifacts, including running containers and dangling volumes"
	@echo "   black               Reformat the whole source code."
	@echo "   deploy              Deploy the whole dashboard, incl. database, importers etc."
	@echo "   develop             Create a deployment, which automatically rebuilds and restarts a container once the source files have been edited."
	@echo "   .env                Set up the environment variables needed for the docker compose / containers themself."
	@echo "   dummy               Do nothing"


# Clean everything up after deployment
clean 0:
	docker compose down -v

black: .venv/builder
	. .venv/builder/bin/activate && \
		black ./code/

deploy: .env black
	docker compose up --build --abort-on-container-failure 

develop d: .env
	docker compose up --build -w

dummy:
	@echo "I don't want to do anything today!"
	
.env: .env.sample
	@echo "The environment variables in the .env file have been set to the default values."
	@echo "You may want to change them according to your requirements."
	cp .env.sample .env

.venv/builder:
	-rm -rf .venv/builder
	python3 -m venv ./.venv/builder
	. .venv/builder/bin/activate && \
		pip install -U pip
