from frontend.components.speech import lines_to_text


def test_lines_to_text_labels_and_skips_blanks():
    text = lines_to_text([{"speaker": "customer", "text": " Hello "}, {"speaker": "agent", "text": "Hi there"},
                          {"speaker": "agent", "text": "  "}])
    assert text == "Customer: Hello\nAgent: Hi there"
