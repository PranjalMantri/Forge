import tiktoken


def get_tokenizer(model: str):
    try:
        encoding = tiktoken.encoding_for_model(model)
        return encoding.encode
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
        return encoding.encode


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def count_tokens(text: str, model: str) -> int:
    tokenizer = get_tokenizer(model)

    if tokenizer:
        return len(tokenizer(text))

    return estimate_tokens(text)


def truncate_text(
    text: str,
    model: str,
    max_tokens: int,
    suffix: str | None = "\n... [Truncated]",
    preserve_lines: bool = True,
):
    tokens = count_tokens(text, model)
    if tokens <= max_tokens:
        return text 

    suffix_tokens = count_tokens(suffix, model)
    target_tokens = max_tokens - suffix_tokens

    if target_tokens <= 0:
        return suffix.strip()

    if preserve_lines:
        return _truncate_by_lines(text, target_tokens, suffix, model)

    return _truncate_by_chars(text, target_tokens, suffix, model)

def _truncate_by_lines(
        text: str,
        target_tokens: int,
        suffix: str,
        model: str
):
    lines = text.split("\n")
    result_lines: list[str] = []
    current_tokens: int = 0

    for line in lines:
        line_tokens = count_tokens(line, model)

        if current_tokens + line_tokens > target_tokens:
            break

        current_tokens += line_tokens
        result_lines.append(line)

    if not result_lines:
        return _truncate_by_chars(text, target_tokens, suffix, model)

    return "\n".join(result_lines) + suffix


def _truncate_by_chars(text: str, target_tokens: int, suffix: str, model: str):
    low = 0
    high = len(text)

    while low <= high:
        mid = (low + high + 1) // 2

        if count_tokens(text[:mid], model) > target_tokens:
            high = mid - 1
        else: 
            low = mid + 1

    return text[:mid] + suffix