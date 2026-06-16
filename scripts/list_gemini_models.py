"""
List available Gemini models using the installed Google GenAI SDK.
Requires `GEMINI_API_KEY` or `GOOGLE_API_KEY` environment variable for Developer API.
"""
import os
import sys

try:
    from google import genai
    Client = genai.Client
    sdk_name = 'google-genai (genai)'
except Exception:
    try:
        import google.generativeai as genai_old
        Client = None
        sdk_name = 'google.generativeai (deprecated)'
    except Exception:
        print('No compatible Google GenAI SDK found (google.genai or google.generativeai).', file=sys.stderr)
        sys.exit(2)

api_key = "AIzaSyASFKVZAtbvh4kswU16yJ7Jos6u9dPo2cU"
if Client is None:
    print(f'Using deprecated SDK {sdk_name}; it may be EOL.', file=sys.stderr)
    print('If you want to list models with the new SDK install `google-genai`.', file=sys.stderr)
    sys.exit(3)

if not api_key:
    print('No API key found. Set GOOGLE_API_KEY or GEMINI_API_KEY in environment and retry.', file=sys.stderr)
    sys.exit(4)

client = Client(api_key=api_key)

print(f'Using SDK: {sdk_name}')
print('Listing models (this may take a moment)...')
try:
    for model in client.models.list():
        # object may have .name or .model or .display_name depending on SDK version
        name = getattr(model, 'name', None) or getattr(model, 'model', None) or getattr(model, 'display_name', None) or repr(model)
        print(name)
except Exception as e:
    print('Error while listing models:', e, file=sys.stderr)
    sys.exit(10)

client.close()
