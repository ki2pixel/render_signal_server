from git_filter_repo import FilteringOptions, GitFilter
import os

options = FilteringOptions.parse_args([
    '--path', 'deployment/public_html/.htaccess',
    '--path', 'deployment/src/GmailMailer.php',
    '--invert-paths',  # Inverser pour supprimer ces chemins
    '--force'          # Forcer l'opération
])

filter_repo = GitFilter(options)
filter_repo.run()
