PYTHON ?= python
IMAGE ?= cryptopulse-dev
GLUE_IMAGE ?= public.ecr.aws/glue/aws-glue-libs:5

.PHONY: install format lint typecheck unit contract test coverage integration build collect build-data dashboard docker-build docker-test glue-test clean

install:
	$(PYTHON) -m pip install -e ".[dev]"

format:
	$(PYTHON) -m ruff check --fix .
	$(PYTHON) -m ruff format .

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

typecheck:
	$(PYTHON) -m mypy src

unit:
	$(PYTHON) -m pytest tests/unit

contract:
	$(PYTHON) -m pytest tests/contract

test:
	$(PYTHON) -m pytest

coverage:
	$(PYTHON) -m pytest --cov=cryptopulse --cov-report=term-missing --cov-report=xml

integration:
	$(PYTHON) -m pytest -m integration tests/integration

build:
	$(PYTHON) -m build

collect:
	$(PYTHON) -m cryptopulse collect all

build-data:
	$(PYTHON) -m cryptopulse build

dashboard:
	$(PYTHON) -m cryptopulse dashboard

docker-build:
	docker build --tag $(IMAGE) .

docker-test: docker-build
	docker run --rm --network none $(IMAGE)

glue-test:
	docker run --rm --network none -v "$(CURDIR):/home/hadoop/workspace" --workdir /home/hadoop/workspace $(GLUE_IMAGE) -c "python3 -m pytest tests/glue"

clean:
	$(PYTHON) -c "from pathlib import Path; import shutil; paths=[*(Path(p) for p in ('.pytest_cache','.mypy_cache','.ruff_cache','.coverage','coverage.xml','build','dist','htmlcov')), *Path('src').glob('*.egg-info')]; [shutil.rmtree(path, ignore_errors=True) if path.is_dir() else path.unlink(missing_ok=True) for path in paths]"
