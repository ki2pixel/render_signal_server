#!/bin/bash
# Script pour exécuter la suite de tests de render_signal_server
# Usage: ./run_tests.sh [options]

set -e

# Couleurs pour l'output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Tests - render_signal_server${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Activer explicitement le venv partagé pour garantir l'accès aux dépendances (fakeredis, etc.).
VENV_PATH="/mnt/venv_ext4/venv_render_signal_server"
if [ -d "$VENV_PATH" ] && [ -f "$VENV_PATH/bin/activate" ]; then
    # shellcheck disable=SC1090
    source "$VENV_PATH/bin/activate"
    PYTHON_BIN="$(command -v python3)"
else
    PYTHON_BIN="python3"
fi

# Fonction pour afficher l'aide
show_help() {
    echo "Usage: ./run_tests.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help           Afficher cette aide"
    echo "  -u, --unit           Exécuter seulement les tests unitaires"
    echo "  -i, --integration    Exécuter seulement les tests d'intégration"
    echo "  -e, --e2e            Exécuter seulement les tests end-to-end"
    echo "  -c, --coverage       Générer un rapport de couverture HTML"
    echo "  -f, --fast           Tests rapides (exclure slow, imap, redis)"
    echo "  -v, --verbose        Mode verbose"
    echo "  -l, --legacy         Exécuter seulement les tests legacy (test_app_render.py)"
    echo "  -n, --new            Exécuter seulement les nouveaux tests (tests/)"
    echo "  -a, --all            Exécuter tous les tests (défaut)"
    echo ""
    echo "Exemples:"
    echo "  ./run_tests.sh                    # Tous les tests"
    echo "  ./run_tests.sh -u -c              # Tests unitaires avec couverture"
    echo "  ./run_tests.sh -f                 # Tests rapides uniquement"
    echo "  ./run_tests.sh -v                 # Mode verbose"
}

# Options par défaut
PYTEST_ARGS=""
COVERAGE=""
MARKER=""
TEST_PATH="tests/ test_app_render.py"

# Parser les arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -u|--unit)
            MARKER="-m unit"
            shift
            ;;
        -i|--integration)
            MARKER="-m integration"
            shift
            ;;
        -e|--e2e)
            MARKER="-m e2e"
            shift
            ;;
        -c|--coverage)
            COVERAGE="--cov=. --cov-report=html --cov-report=term-missing"
            shift
            ;;
        -f|--fast)
            MARKER="-m 'not slow and not imap and not redis'"
            shift
            ;;
        -v|--verbose)
            PYTEST_ARGS="$PYTEST_ARGS -vv"
            shift
            ;;
        -l|--legacy)
            TEST_PATH="test_app_render.py"
            shift
            ;;
        -n|--new)
            TEST_PATH="tests/"
            shift
            ;;
        -a|--all)
            TEST_PATH="tests/ test_app_render.py"
            shift
            ;;
        *)
            echo -e "${RED}Option inconnue: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Vérifier que pytest est installé
if ! "$PYTHON_BIN" -m pytest --version &> /dev/null; then
    echo -e "${RED}Erreur: pytest n'est pas installé${NC}"
    echo "Installer les dépendances avec: pip install -r requirements-dev.txt"
    exit 1
fi

# Construire la commande pytest
CMD="$PYTHON_BIN -m pytest $TEST_PATH $PYTEST_ARGS $MARKER $COVERAGE"

echo -e "${YELLOW}Commande: $CMD${NC}"
echo ""

# Exécuter les tests
$CMD

# Résultat
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  ✓ Tous les tests sont passés !${NC}"
    echo -e "${GREEN}========================================${NC}"
    
    if [ ! -z "$COVERAGE" ]; then
        echo ""
        echo -e "${YELLOW}Rapport de couverture HTML généré dans: htmlcov/index.html${NC}"
    fi
else
    echo ""
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}  ✗ Certains tests ont échoué${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi
