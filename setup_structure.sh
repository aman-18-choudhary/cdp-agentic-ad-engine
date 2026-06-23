#!/usr/bin/env bash
# Creates the full project directory tree and empty placeholder files
# Run from project root: ./setup_structure.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Creating project structure at: $PROJECT_ROOT"

# Directory tree
dirs=(
    "data"
    "simulators"
    "consumers"
    "uid_engine"
    "agents"
    "vector_store"
    "api"
    "k8s"
    "infra"
    "tests"
    "common"
    "scripts"
    ".github/workflows"
)

for dir in "${dirs[@]}"; do
    mkdir -p "$PROJECT_ROOT/$dir"
    echo "Created: $dir/"
done

# Empty placeholder files (will be populated later)
files=(
    "simulators/platform_a_producer.py"
    "simulators/platform_b_producer.py"
    "consumers/event_consumer.py"
    "uid_engine/deterministic.py"
    "uid_engine/probabilistic.py"
    "uid_engine/merger.py"
    "uid_engine/evaluate.py"
    "agents/intent_profiler.py"
    "agents/product_matcher.py"
    "agents/ad_creative.py"
    "vector_store/embed_catalog.py"
    "api/main.py"
    "k8s/consumer-deployment.yaml"
    "k8s/keda-scaledobject.yaml"
    "infra/main.tf"
    "infra/variables.tf"
    "infra/outputs.tf"
    "tests/test_uid_engine.py"
    "tests/test_agents.py"
    "tests/test_api.py"
    "scripts/prepare_data.py"
    "Dockerfile"
    "docker-compose.yml"
    "requirements.txt"
    "pyproject.toml"
    ".env.example"
    ".github/workflows/ci.yml"
    "README.md"
)

for file in "${files[@]}"; do
    touch "$PROJECT_ROOT/$file"
    echo "Created: $file"
done

# Make scripts executable
chmod +x "$PROJECT_ROOT/setup_structure.sh"
chmod +x "$PROJECT_ROOT/scripts/prepare_data.py" 2>/dev/null || true

echo ""
echo "✅ Project structure created successfully"
echo ""
echo "Next steps:"
echo "  1. Fill in docker-compose.yml, requirements.txt, common/schemas.py, common/logging.py, .env.example"
echo "  2. Run: docker-compose up -d"
echo "  3. Run: python scripts/prepare_data.py (after placing Kaggle CSVs in data/)"