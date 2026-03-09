from tools.diff_transcript import diff_transcript

expected = "Call 1-800-555-0199 and ask for Dr. Nguyen. She will walk you through the 14.5% interest rate and the 30-day clause."

# This is what Whisper actually returned from our test
actual = "Call 1-800-555-5199, and ask for Dr. Nguyen. She will walk you through the 14.5% interest rate and the 30-day clause."

result = diff_transcript.invoke({
    "expected_script": expected,
    "actual_transcript": actual
})

print("=== ACCURACY ===")
print(f"WER:      {result['wer']}  (0 = perfect, 1 = everything wrong)")
print(f"Accuracy: {result['accuracy_pct']}%")

print("\n=== ERROR COUNTS ===")
for k, v in result['error_counts'].items():
    print(f"  {k}: {v}")

print("\n=== WORD DIFF ===")
for op in result['diff_ops']:
    if op['op'] == 'equal':
        print(f"  ✅ {op['expected']}")
    elif op['op'] == 'replace':
        print(f"  ❌ WRONG:   expected '{op['expected']}' got '{op['actual']}'")
    elif op['op'] == 'delete':
        print(f"  ❌ MISSING: '{op['expected']}'")
    elif op['op'] == 'insert':
        print(f"  ❌ EXTRA:   '{op['actual']}'")