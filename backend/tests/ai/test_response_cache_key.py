from app.ai.cache import AIResponseCache


def test_response_cache_key_includes_top_p() -> None:
    messages = [{"role": "user", "content": "Hello"}]

    key_top_p_default = AIResponseCache._generate_cache_key(
        provider_code="openai",
        model="gpt-5.4",
        messages=messages,
        temperature=0.0,
        top_p=1.0,
        max_tokens=64,
        tools=None,
        tool_choice=None,
    )
    key_top_p_low = AIResponseCache._generate_cache_key(
        provider_code="openai",
        model="gpt-5.4",
        messages=messages,
        temperature=0.0,
        top_p=0.5,
        max_tokens=64,
        tools=None,
        tool_choice=None,
    )
    key_top_p_repeat = AIResponseCache._generate_cache_key(
        provider_code="openai",
        model="gpt-5.4",
        messages=messages,
        temperature=0.0,
        top_p=1.0,
        max_tokens=64,
        tools=None,
        tool_choice=None,
    )

    assert key_top_p_default != key_top_p_low
    assert key_top_p_default == key_top_p_repeat
