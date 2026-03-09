from gtts import gTTS

# This is our test script — deliberately contains things that trip up TTS:
# - a phone number
# - an abbreviation (Dr.)
# - a foreign name (Nguyen)
# - a percentage
text = "Call 1-800-555-0199 and ask for Dr. Nguyen. She will walk you through the 14.5% interest rate and the 30-day clause."

print(f"Generating audio for: '{text}'")

tts = gTTS(text=text, lang='en', slow=False)
tts.save("test_audio.wav")

print("Saved to test_audio.wav")