from app.core import prompt


def test_extraction_prompt_names_the_person() -> None:
    text = prompt.EXTRACTION_SYSTEM_PROMPT.format(person="Grandpa Tom")
    assert "memories about Grandpa Tom, who has passed away" in text
    # Only {person} is a placeholder, so no stray braces survive formatting
    assert "{" not in text


def test_answer_prompt_puts_the_memories_before_the_question() -> None:
    text = prompt.ANSWER_USER_PROMPT.format(
        context="[1] Dad fished.", question="What did Dad do?"
    )
    assert text == "Memories:\n[1] Dad fished.\n\nQuestion: What did Dad do?"


def test_answer_system_prompt_forbids_guessing() -> None:
    assert "ONLY" in prompt.ANSWER_SYSTEM_PROMPT
    assert "do not know" in prompt.ANSWER_SYSTEM_PROMPT


def test_describe_image_prompt_only_asks_for_what_is_visible() -> None:
    assert "Only state what you can see" in prompt.DESCRIBE_IMAGE_PROMPT
