# Makefile — Hermes Stack Sanitization Automation
# ================================================
# PID: pavel_20260619_200039
#
# Usage:
#   make sanitize    — Full sanitization pipeline
#   make copy        — Copy sources only
#   make replace     — Replace PII in copied files
#   make verify      — Run verification checks
#   make docs        — Generate README + SANITIZATION_LOG
#   make clean       — Remove her2code/ target directory
#   make all         — clean + sanitize
#
# NOTE: Update TARGET_DIR in sanitize-config.yaml before running.
# The default target uses /home/user/ paths which must be changed.

.PHONY: all sanitize copy replace verify docs clean

# Default target
all: clean sanitize

# Full sanitization pipeline
sanitize:
	@echo "=== Hermes Stack Sanitization ==="
	python3 sanitize.py

# Copy sources only
copy:
	python3 sanitize.py --copy-only

# Replace PII only (on already-copied files)
replace:
	python3 sanitize.py --replace-only

# Verification checks
verify:
	python3 sanitize.py --verify-only

# Generate documentation only
docs:
	@echo "=== Generating README.md and SANITIZATION_LOG.md ==="
	python3 -c "
import sanitize
config = sanitize.load_config('sanitize-config.yaml')
target_dir = sanitize.resolve_path(config['target_dir'])
readme = sanitize.generate_readme(config)
with open(f'{target_dir}/README.md', 'w') as f:
    f.write(readme)
print('README.md generated')
log = sanitize.generate_sanitization_log(config, [], [])
with open(f'{target_dir}/SANITIZATION_LOG.md', 'w') as f:
    f.write(log)
print('SANITIZATION_LOG.md generated')
"

# Remove her2code/ target directory (WARNING: destructive!)
clean:
	@echo "=== Cleaning target directory ==="
	@echo "WARNING: This removes the sanitized output. Source files are NOT affected."
	@echo "To specify target, edit sanitize-config.yaml target_dir."
	python3 -c "
import sanitize, shutil, os
config = sanitize.load_config('sanitize-config.yaml')
target = sanitize.resolve_path(config['target_dir'])
if os.path.exists(target):
    shutil.rmtree(target)
    print(f'Removed: {target}')
else:
    print(f'Target not found: {target}')
"
