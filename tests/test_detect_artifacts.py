from tools.detect_audio_artifacts import detect_audio_artifacts

result = detect_audio_artifacts.invoke({"audio_path": "test_audio.wav"})

print("=== AUDIO ARTIFACT REPORT ===")
print(f"Overall clean: {result['overall_clean']}")
print(f"Artifacts found: {result['artifact_count']}")

print("\n=== RAW MEASUREMENTS ===")
print(f"Clipping:    {result['clipping_pct']}% of samples")
print(f"DC offset:   {result['dc_offset']}")
print(f"Noise ratio: {result['noise_ratio']}")
print(f"Pop count:   {result['pop_count']}")

if result['artifact_count'] > 0:
    print("\n=== FLAGGED ARTIFACTS ===")
    for a in result['artifacts']:
        print(f"  ⚠️  [{a['severity'].upper()}] {a['type']}: {a['detail']}")
else:
    print("\n✅ No artifacts detected")