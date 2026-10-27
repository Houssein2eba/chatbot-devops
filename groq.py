import os

from openai import OpenAI


def ask_groq(question: str, context: str = "") -> str:
    """Send a request to Groq and return the answer text."""
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Set GROQ_API_KEY before calling ask_groq().")

    prompt = question
    if context:
        prompt = (
            "Use the supplied document context to answer the question. "
            "If the context doesn't contain the answer, say so clearly.\n\n"
            f"Context:\n{context}\n\nQuestion:\n{question}"
        )

    client = OpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=api_key,
    )
    response = client.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        messages=[
            {"role": "system", "content": "You are a precise DevOps documentation assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()


if __name__ == "__main__":
    print(ask_groq("Hello, Groq!"))
