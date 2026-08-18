#!/bin/sh
# Migrationen vor jedem Start anwenden -- idempotent (Alembic überspringt bereits
# angewendete Revisionen), deshalb unbedenklich bei jedem Container-Neustart.
set -e

alembic upgrade head

exec "$@"
