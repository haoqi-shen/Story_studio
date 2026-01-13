import os
import openai

from story_studio.controller import run_story_session

"""
Before submitting the assignment, describe here in a few sentences what you would have built next if you spent 2 more hours on this project:

"""


def call_model(prompt: str, max_tokens=3000, temperature=0.1) -> str:
    openai.api_key = os.getenv("OPENAI_API_KEY")  # do not hardcode keys
    resp = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": prompt}],
        stream=False,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return resp.choices[0].message["content"]  # type: ignore


def main():
    user_input = input("What kind of bedtime story do you want to hear? ").strip()
    if not user_input:
        user_input = "A cozy bedtime story about a friendly cat who finds a safe home."

    _, session_path = run_story_session(
        user_request=user_input,
        model_fn=call_model,
        enable_hitl=True,
        verbose=True,   # ✅ prints real-time progress + final story
        debug=False,    # set True to see truncated spec/plan + top issues
    )

    print(f"Session saved: {session_path}")


if __name__ == "__main__":
    main()
