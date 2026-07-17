.PHONY: up test demo
up:
	docker compose up --build
test:
	python -m unittest discover -s tests -v
demo:
	python -m scripts.demo_run
