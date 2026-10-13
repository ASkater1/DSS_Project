# Variables

help:
	@echo "Please use 'make <target>' where <target> is one of:"
	@echo "   clean               to remove all artifacts, including running containers and dangling volumes"
	@echo "   deploy              to deploy the whole dashboard, incl. database, importers etc."
	@echo "   develop             create a deployment, which automatically rebuilds and restarts a container once the source files have been edited."
	@echo "   .env                set up the environment variables needed for the docker compose / containers themself."

# Clean everything up after deployment
clean 0:
	docker compose down -v

# Actually deploy everything
deploy: .env
	docker compose up --build --abort-on-container-failure 

develop d: .env
	docker compose up --build -w
	
.env: .env.sample
	@echo "The environment variables in the .env file have been set to the default values."
	@echo "You may want to change them according to your requirements."
	cp .env.sample .env