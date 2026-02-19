import os
import sys

def main():
    try:
        import openai
    except Exception:
        print("ERROR:openai_not_installed")
        sys.exit(2)

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("ERROR:no_openai_api_key")
        sys.exit(2)

    # Support both openai v1 (openai.OpenAI client) and older APIs
    try:
        # v1 style
        OpenAI = getattr(openai, "OpenAI", None)
        if OpenAI is not None:
            client = OpenAI(api_key=key)
            try:
                models = client.models.list()
                n = len(getattr(models, 'data', []))
                print(f"OK:models_listed:{n}")
                sys.exit(0)
            except Exception:
                # fallback to chat completion with v1 client
                try:
                    resp = client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "ping"}], temperature=0)
                    # summarize response
                    txt = str(resp)
                    print("OK:chat_ping:response_received")
                    sys.exit(0)
                except Exception as e:
                    print("ERROR:api_call_failed:" + str(e).replace('\n', ' '))
                    sys.exit(3)
        else:
            # older openai package
            try:
                openai.api_key = key
                # try listing models
                models = openai.Model.list()
                n = len(getattr(models, 'data', models.get('data', []))) if models else 0
                print(f"OK:models_listed:{n}")
                sys.exit(0)
            except Exception:
                try:
                    resp = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=[{"role": "user", "content": "ping"}], temperature=0)
                    content = resp['choices'][0]['message']['content']
                    print("OK:chat_ping:" + content.strip()[:200])
                    sys.exit(0)
                except Exception as e:
                    print("ERROR:api_call_failed:" + str(e).replace('\n', ' '))
                    sys.exit(3)
    except Exception as e:
        print("ERROR:unexpected:" + str(e).replace('\n', ' '))
        sys.exit(4)

if __name__ == '__main__':
    main()
