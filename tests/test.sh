#!/usr/bin/env bash
# Run against a disposable instance: the acceptance cases replace test tables.
set -euo pipefail
cd "$(dirname "$0")/.."
TESTFILE=$(mktemp)
RESULTFILE=$(mktemp)
trap 'rm -f "$TESTFILE" "$RESULTFILE"' EXIT

cat > "$TESTFILE" <<'ENDOFTESTS'
write "CASE:import",!  write ##class(dc.kaggleloader.Loader).Load("unsdsn/world-happiness/versions/2","KaggleData.acceptance",0,"replace"),!!  write "CASE:info",!  write ##class(dc.kaggleloader.Loader).Info("unsdsn/world-happiness/versions/2"),!!  write "CASE:invalid",!  write ##class(dc.kaggleloader.Loader).Load("just-one-part"),!!  write "CASE:pinned",!  write ##class(dc.kaggleloader.Loader).Load("unsdsn/world-happiness/versions/2","KaggleData.pinned",0,"replace"),!!  write "CASE:fail",!  write ##class(dc.kaggleloader.Loader).Load("unsdsn/world-happiness/versions/2","KaggleData.pinned",0,"fail"),!!  write "CASE:limit",!  write ##class(dc.kaggleloader.Loader).Load("unsdsn/world-happiness/versions/2","KaggleData.limited",10,"replace"),!!
halt
ENDOFTESTS

echo '=== iris-kaggle-import acceptance tests ==='
docker compose exec -T iris iris session IRIS -U USER < "$TESTFILE" | tee "$RESULTFILE"
python3 tests/verify_acceptance.py "$RESULTFILE"

# Check stored data independently of the import result summary.
ROWS=$(docker compose exec -T iris bash -c 'echo "SELECT COUNT(*) FROM KaggleData.limited_2015" | iris sql IRIS -U USER' | grep -oE '^\| [0-9]+' | head -1 | grep -oE '[0-9]+' || true)
if [ "$ROWS" != '10' ]; then
    echo "FAIL: limited table row count: ${ROWS:-missing}"
    exit 1
fi
echo 'PASS: limited table contains 10 rows'
