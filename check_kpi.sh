#!/bin/bash
# Quick KPI checker for Chapter 3 vs 3.1

echo "========================================="
echo "Chapter 3 vs 3.1 KPI Comparison"
echo "========================================="
echo ""

sqlite3 medical_coding.db <<EOF
.mode column
.headers on
SELECT
    'Chapter 3' as Chapter,
    COUNT(*) as Total,
    SUM(CASE WHEN confidence > 0 THEN 1 ELSE 0 END) as Correct,
    ROUND(AVG(confidence) * 100, 1) || '%' as Correctness
FROM reverse_predictions
UNION ALL
SELECT
    'Chapter 3.1' as Chapter,
    COUNT(*) as Total,
    SUM(CASE WHEN confidence > 0 THEN 1 ELSE 0 END) as Correct,
    ROUND(AVG(confidence) * 100, 1) || '%' as Correctness
FROM rag_enhanced_predictions;
EOF

echo ""
echo "Improvement:"
sqlite3 medical_coding.db <<EOF
SELECT
    ROUND((SELECT AVG(confidence) * 100 FROM rag_enhanced_predictions) -
          (SELECT AVG(confidence) * 100 FROM reverse_predictions), 1) || ' percentage points'
    as Correctness_Gain;
EOF
