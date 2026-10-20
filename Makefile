
help:
	@echo "Please use 'make <target>' where <target> is one of:"
	@echo "   clean               Remove all artifacts, including running containers and dangling volumes"
	@echo "   black               Reformat the whole source code."
	@echo "   deploy              Deploy the whole dashboard, incl. database, importers etc."
	@echo "   develop             Create a deployment, which automatically rebuilds and restarts a container once the source files have been edited."
	@echo "   documentation       Rebuild the documentation for the Project."
	@echo "   .env                Set up the environment variables needed for the docker compose / containers themself."
	@echo "   dummy               Do nothing"


# Clean everything up after deployment
clean 0:
	docker compose down -v
	$(MAKE) -C ./documentation clean


black: .venv/builder
	. .venv/builder/bin/activate && \
		black ./code/

deploy: .env #black
	docker compose up 
	#--abort-on-container-failure 

develop d: .env
	docker compose up --build -w

documentation docu: .env .venv/builder
	$(MAKE) -C ./documentation singlehtml

dummy:
	@echo "I don't want to do anything today!"
	
.env: .env.sample
	@echo "The environment variables in the .env file have been set to the default values."
	@echo "You may want to change them according to your requirements."
	cp .env.sample .env

.venv/builder venv:
	-rm -rf .venv/builder
	python3 -m venv ./.venv/builder
	. .venv/builder/bin/activate && \
		pip install -U pip && \
		pip install -r code/builder/requirements.txt

